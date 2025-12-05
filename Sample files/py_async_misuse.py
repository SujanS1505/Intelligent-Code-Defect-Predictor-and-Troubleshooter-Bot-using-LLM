import asyncio
async def compute():
    await asyncio.sleep(0.1)
    return 42
def main():
    # BUG: calling coroutine without awaiting or running loop
    result = compute()
    print('result:', result)  # <coroutine object ...>
main()
