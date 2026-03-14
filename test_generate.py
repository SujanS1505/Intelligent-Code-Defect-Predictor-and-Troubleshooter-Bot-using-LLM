import os
os.environ["GEMINI_API_KEY"] = "AIzaSyBk4cfhiJ4wpFKOGo9zaHWKaPZRergVgu0"
import logging
logging.basicConfig(level=logging.DEBUG)

from rag import gemini_api
result = gemini_api.generate_fix(
    lang="python",
    path="test.py",
    issue="bug",
    span="line 1",
    code="nums=[1,2,3]\nprint(nums[3])",
    passages=[]
)
print(f"RESULT: {result}")
