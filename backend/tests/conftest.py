"""讓 pytest 能匯入 `app`（把 backend/ 加入 sys.path）。

無論從專案根目錄或 backend/ 啟動 pytest，皆可 `import app`。
"""
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent  # .../backend
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
