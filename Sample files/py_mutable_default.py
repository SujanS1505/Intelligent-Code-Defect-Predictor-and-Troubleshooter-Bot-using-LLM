def append_item(x, items=[]):
    items.append(x)  # BUG: mutable default accumulates across calls
    return items

print(append_item(1))
print(append_item(2))  # expects [2], gets [1,2]
