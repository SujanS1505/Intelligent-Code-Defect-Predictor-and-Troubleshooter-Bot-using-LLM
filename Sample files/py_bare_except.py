def risky():
    try:
        1/0
    except:  # BUG: swallows all exceptions, hides root cause
        pass
risky()
print('continued with silent failure')
