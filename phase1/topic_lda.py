"""LDA 主题建模（可配置分词与停用词/噪音词过滤）。"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import CountVectorizer

from phase1.config import OUT, ROOT
from phase1.lexicons import EMOJI_RE, XHS_BRACKET

try:
    import jieba  # type: ignore
except ImportError:  # pragma: no cover - 兼容无 jieba 环境
    jieba = None

_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_AT_USER_RE = re.compile(r"@[\w\u4e00-\u9fff_-]+")
_DIGIT_ID_RE = re.compile(r"\b\d{5,}\b")
_PURE_PUNCT_RE = re.compile(r"^[\W_]+$")

_ZH_STOPWORDS = ROOT / "config" / "topic_modeling" / "general_stopwords.txt"
_PLATFORM_NOISE = ROOT / "config" / "topic_modeling" / "platform_noise_tokens.csv"
_CORPUS_NOISE = ROOT / "config" / "topic_modeling" / "corpus_noise_tokens.csv"
_USER_DICT = ROOT / "config" / "topic_modeling" / "domain_user_dict.txt"


@dataclass
class LDARunResult:
    topics_terms: pd.DataFrame
    topic_by_category: pd.DataFrame
    topic_samples: pd.DataFrame
    diagnostics: pd.DataFrame


def _load_lines(path: Path) -> set[str]:
    if not path.exists():
        return set()
    vals = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        v = line.strip()
        if v and not v.startswith("#"):
            vals.add(v)
    return vals


def _load_noise_tokens(path: Path) -> set[str]:
    if not path.exists():
        return set()
    df = pd.read_csv(path)
    if "token" not in df.columns:
        return set()
    if "keep_in_topic" in df.columns:
        df = df[df["keep_in_topic"].astype(str).str.lower() != "true"]
    return set(df["token"].dropna().astype(str).str.strip().tolist())


def load_topic_stopwords(
    stopwords_path: Path = _ZH_STOPWORDS,
    platform_noise_path: Path = _PLATFORM_NOISE,
    corpus_noise_path: Path = _CORPUS_NOISE,
) -> set[str]:
    return (
        _load_lines(stopwords_path)
        | _load_noise_tokens(platform_noise_path)
        | _load_noise_tokens(corpus_noise_path)
    )


def _setup_tokenizer(tokenizer: str, user_dict_path: Path = _USER_DICT) -> str:
    tokenizer = tokenizer.lower().strip()
    if tokenizer == "jieba":
        if jieba is None:
            raise ImportError(
                "tokenizer='jieba' 但当前环境未安装 jieba。"
                "请先安装 requirements.txt 依赖，或显式使用 tokenizer='char_bigram' 进行兜底实验。"
            )
        if user_dict_path.exists():
            jieba.load_userdict(str(user_dict_path))
        return tokenizer
    if tokenizer == "pkuseg":
        try:
            import pkuseg  # type: ignore
        except ImportError as exc:
            raise ImportError("tokenizer='pkuseg' 需要先安装 pkuseg") from exc
        return tokenizer
    if tokenizer == "char_bigram":
        return tokenizer
    raise ValueError(f"不支持的 tokenizer: {tokenizer}")


def clean_text(text: str) -> str:
    t = str(text or "")
    t = _URL_RE.sub(" ", t)
    t = _AT_USER_RE.sub(" ", t)
    t = _DIGIT_ID_RE.sub(" ", t)
    t = EMOJI_RE.sub(" ", t)
    t = XHS_BRACKET.sub(" ", t)
    t = t.lower()
    t = re.sub(r"\s+", " ", t).strip()
    return t


def tokenize_text(
    text: str,
    *,
    tokenizer: str = "jieba",
    stopwords: set[str] | None = None,
    keep_single_chars: set[str] | None = None,
) -> list[str]:
    t = clean_text(text)
    if not t:
        return []

    if tokenizer == "char_bigram":
        # 仅作无法安装中文分词器时的兜底，不建议用于正式可解释性分析
        seqs = re.findall(r"[\u4e00-\u9fff]{2,}", t)
        tokens: list[str] = []
        for seq in seqs:
            if len(seq) == 2:
                tokens.append(seq)
            else:
                tokens.extend(seq[i : i + 2] for i in range(len(seq) - 1))
        tokens.extend(re.findall(r"[a-z0-9]{2,}", t))
    elif tokenizer == "jieba":
        tokens = jieba.lcut(t, cut_all=False)
    elif tokenizer == "pkuseg":
        import pkuseg  # type: ignore

        tokens = pkuseg.pkuseg().cut(t)
    else:
        raise ValueError(f"不支持的 tokenizer: {tokenizer}")

    stop = stopwords or set()
    keep_single = keep_single_chars or {"人", "机", "狗"}
    filtered: list[str] = []
    for tok in tokens:
        w = tok.strip()
        if not w:
            continue
        if w in stop:
            continue
        if _PURE_PUNCT_RE.match(w):
            continue
        if tokenizer != "char_bigram" and len(w) == 1 and w not in keep_single:
            continue
        if EMOJI_RE.search(w):
            continue
        filtered.append(w)
    return filtered


def build_topic_documents(
    df: pd.DataFrame,
    *,
    content_col: str = "content",
    tokenizer: str = "jieba",
    min_tokens: int = 3,
    stopwords: set[str] | None = None,
) -> pd.DataFrame:
    effective_tokenizer = _setup_tokenizer(tokenizer)
    sw = stopwords or load_topic_stopwords()

    data = df.copy()
    data[content_col] = data[content_col].fillna("").astype(str)
    data["tokens"] = data[content_col].map(
        lambda s: tokenize_text(s, tokenizer=effective_tokenizer, stopwords=sw)
    )
    data["clean_token_count"] = data["tokens"].map(len)
    data["is_noise_for_topic"] = data["clean_token_count"] < min_tokens
    data = data.loc[~data["is_noise_for_topic"]].copy()
    data["content_clean"] = data["tokens"].map(lambda x: " ".join(x))
    return data


def _topic_terms(lda: LatentDirichletAllocation, feature_names: np.ndarray, topn: int = 15) -> pd.DataFrame:
    rows = []
    for tid, comp in enumerate(lda.components_):
        top_idx = np.argsort(comp)[-topn:][::-1]
        rows.append({"topic": tid, "top_terms": ", ".join(feature_names[top_idx])})
    return pd.DataFrame(rows)


def run_lda(
    df: pd.DataFrame,
    *,
    tokenizer: str = "jieba",
    n_topics: int = 10,
    min_df: int = 10,
    max_df: float = 0.5,
    max_features: int = 8000,
    max_iter: int = 30,
    random_state: int = 42,
    sample_per_topic: int = 30,
    top_terms: int = 15,
) -> LDARunResult:
    topic_df = build_topic_documents(df, tokenizer=tokenizer)
    if topic_df.empty:
        raise ValueError("LDA 输入为空，请放宽清洗条件或检查数据。")

    vec = CountVectorizer(
        analyzer=lambda s: s.split(),
        min_df=min_df,
        max_df=max_df,
        max_features=max_features,
    )
    X = vec.fit_transform(topic_df["content_clean"].tolist())

    lda = LatentDirichletAllocation(
        n_components=n_topics,
        learning_method="batch",
        max_iter=max_iter,
        random_state=random_state,
        doc_topic_prior=1.0 / n_topics,
        topic_word_prior=0.01,
    )
    doc_topic = lda.fit_transform(X)
    topic_label = doc_topic.argmax(axis=1).astype(int)
    topic_df["topic"] = topic_label
    topic_df["topic_prob"] = doc_topic.max(axis=1)

    feature_names = np.array(vec.get_feature_names_out())
    terms = _topic_terms(lda, feature_names, topn=top_terms)

    topic_size = topic_df.groupby("topic").size().rename("size").reset_index()
    topics_terms = terms.merge(topic_size, on="topic", how="left").fillna({"size": 0})
    topics_terms["size"] = topics_terms["size"].astype(int)

    by_cat = (
        topic_df.groupby(["topic", "post_category"])
        .size()
        .rename("count")
        .reset_index()
        .sort_values(["topic", "count"], ascending=[True, False])
    )
    by_cat["share"] = by_cat["count"] / by_cat.groupby("topic")["count"].transform("sum")

    sample = (
        topic_df.sort_values(["topic", "topic_prob", "like_count"], ascending=[True, False, False])
        .groupby("topic")
        .head(sample_per_topic)
    )
    topic_samples = sample[
        [
            "topic",
            "topic_prob",
            "post_category",
            "comment_level",
            "like_count",
            "content",
        ]
    ].copy()

    diagnostics = pd.DataFrame(
        [
            {"metric": "n_docs", "value": float(topic_df.shape[0])},
            {"metric": "vocab_size", "value": float(len(feature_names))},
            {"metric": "n_topics", "value": float(n_topics)},
            {"metric": "perplexity", "value": float(lda.perplexity(X))},
        ]
    )
    return LDARunResult(
        topics_terms=topics_terms,
        topic_by_category=by_cat,
        topic_samples=topic_samples,
        diagnostics=diagnostics,
    )


def scan_lda_k(
    df: pd.DataFrame,
    *,
    tokenizer: str = "jieba",
    k_values: Iterable[int] = (5, 8, 10, 12, 15),
    min_df: int = 10,
    max_df: float = 0.5,
) -> pd.DataFrame:
    docs = build_topic_documents(df, tokenizer=tokenizer)
    if docs.empty:
        raise ValueError("LDA 输入为空，无法扫描 K。")

    vec = CountVectorizer(
        analyzer=lambda s: s.split(),
        min_df=min_df,
        max_df=max_df,
        max_features=8000,
    )
    X = vec.fit_transform(docs["content_clean"].tolist())
    rows = []
    for k in k_values:
        lda = LatentDirichletAllocation(
            n_components=k,
            learning_method="batch",
            max_iter=25,
            random_state=42,
            doc_topic_prior=1.0 / k,
            topic_word_prior=0.01,
        )
        doc_topic = lda.fit_transform(X)
        labels = doc_topic.argmax(axis=1)
        counts = np.bincount(labels, minlength=k)
        rows.append(
            {
                "k": k,
                "perplexity": float(lda.perplexity(X)),
                "largest_topic_share": float(counts.max() / counts.sum()),
                "smallest_topic_share": float(counts.min() / counts.sum()),
            }
        )
    return pd.DataFrame(rows).sort_values("k")


def export_lda_result(
    result: LDARunResult,
    *,
    prefix: str = "lda",
    output_dir: Path = OUT,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    result.topics_terms.to_csv(output_dir / f"{prefix}_topics_terms.csv", index=False)
    result.topic_by_category.to_csv(output_dir / f"{prefix}_topic_by_category.csv", index=False)
    result.topic_samples.to_csv(output_dir / f"{prefix}_topic_samples.csv", index=False)
    result.diagnostics.to_csv(output_dir / f"{prefix}_diagnostics.csv", index=False)
