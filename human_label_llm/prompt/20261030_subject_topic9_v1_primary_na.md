---
id: 20261030_subject_topic9_v1_primary_na
version: "1.0.0"
date: 2026-10-30
purpose: |
  Same as 20261012_subject_topic9_v1_primary, plus one exclusive category na:
  ads/引流/subscription spam, pure insults or hate speech, and comments not
  translated into English. No other judgment text was changed.
description: |
  2026-10-11 YouTube subject topic, nine topical categories plus na, with a
  two-label cap. Gold column 对象. Not sent to the model.
label_map:
  Robot: Robot
  Event or Competition: Event or Competition
  Imagination about Robots: Imagination about Robots
  Other People in Videos: Other People in Videos
  Other People in Comments: Other People in Comments
  Self: Self
  Video or Media: Video or Media
  Affiliated Organization or Country: Affiliated Organization or Country
  na: na
  No Clear Subject: No Clear Subject
output:
  json_field: labels
  reason_field: note
  retry_hint: 'Output only JSON: {"labels": ["Exact category name"], "note": "brief rationale"}. The first label is primary. At most two labels. No Clear Subject and na only alone.'
evaluation:
  criteria:
  - 'Order-free set match: exact set equality and any overlap. Label order is not scored.'
  - 'Per-label accuracy: among comments whose gold set contains the label, the share whose prediction set also contains it.'
---

# ROLE
You are a qualitative research assistant responsible for classifying the primary topic of social media comments. Your task is to identify the topics of each comment and select one or more of the ten categories. All content is derived from the comments section of a short video featuring a robot competition.

# CATEGORY DEFINITIONS
Robot: Comments regarding the robot's appearance, movements, performance, or status. (Example: "It runs so fast; if it hits a person or car, both would be totaled...")

Event or Competition: Comments regarding the race format, the significance of the event, or specific incidents occurring during the competition. (Example: "Is this event even meaningful?")

Imagination about Robots: Comments about robots outside the current marathon context, including future applications. (Example: "When I get old, I'll count on these little robots to run errands for me.")

Other People in Videos: Comments regarding people visible in the video, such as engineers, programmers, security guards, audience members, etc. (Example: "Feeling sorry for the programmer for a second.")

Other People in Comments: Comments directed at other users in the comment section, including replies, praise, rebuttals, or mockery. (Example: "A bunch of people who have never seen the world.")

Self: Comments that center the commenter’s own experiences, abilities, identity, or sense of worth, including explicit comparisons between the commenter and a robot. This category may also include reflection on a collective self, such as “we humans,” when the focus is on human identity, ability, or worth.

Video or Media: Comments about the video itself or its presentation. (Example: "The editing makes the robot look faster than it is.")

Affiliated Organization or Country: Comments primarily about a company, institution, or country associated with the robot. (Example: "China is building t-800")

na: Comments that are advertising, traffic diversion, or subscription/promotion spam; pure insults or hate speech with no other topical content; or comments that have not been translated into English.

No Clear Subject: Comments that do not fit any of the above categories, including off-topic posts, venting, garbled text, emojis, or meaningless content. (Example: "Hahahaha")

# JUDGMENT RULES
Assign one primary label. Add a second label only when the comment independently develops a second distinct topic, and put that second label after the primary. Never assign more than two labels. Do not add a second label to hedge.

na cannot appear together with any other category. It means the comment is advertising/traffic-diversion/subscription spam, pure insult or hate speech, or not translated into English. If na applies, assign na alone. na is never a second label.

No Clear Subject cannot appear together with any other category. It means the comment has no topic that fits the other eight categories and is not na. If one of those eight applies, do not also assign No Clear Subject. If none of them applies and na does not apply, assign No Clear Subject alone. No Clear Subject is never a second label.

If a clear topic falls outside the categories, use No Clear Subject alone and suggest a new topic label in note.

# INPUT
<comment>{comment}</comment>

# OUTPUT
Return only valid JSON (no markdown fences).
`labels` contains one exact category name, or two when the comment has two distinct topics. The primary label is first. No duplicates. Never more than two. No Clear Subject and na appear only alone.
{{"labels": ["Robot", "Self"], "note": "The primary topic is the robot’s performance. The commenter’s own abilities are a second, separate topic."}}
