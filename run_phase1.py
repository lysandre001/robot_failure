#!/usr/bin/env python3
"""从项目根目录运行：
  python run_phase1.py
  python run_phase1.py --xlsx data/2604-小红书/小红书帖子数据.xlsx
也可设置环境变量 ROBOTIC_FAILURE_XLSX。"""
from phase1.pipeline import main

if __name__ == "__main__":
    main()
