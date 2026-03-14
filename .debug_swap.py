code = '''def defective_sort(arr):
    n = len(arr)
    for i in range(n):
        for j in range(n - i):
            if arr[j] > arr[j + 1]:
                arr[j] = arr[j + 1]
                arr[j + 1] = arr[j]
    return arr'''

lines = code.splitlines()
for i, line in enumerate(lines):
    print(f'{i}: repr={repr(line)} | stripped={repr(line.strip())}')
