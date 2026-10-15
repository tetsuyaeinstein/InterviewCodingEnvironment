def is_valid(s):
    pairs = {
        ")":"(",
        "}":"{",
        "]":"["
    }

    stack = []
    for char in s:
        if char in "({[":
            stack.append(char)
        elif char in pairs:
            if not stack or stack.pop() != pairs[char]:
                return False

    return not stack

# print(is_valid("Hel{lo}"))

a = {"transaction_id": "T-9", "amount": "4.00"}
print(a.keys)
print(a["transaction_id"])

print(a.get("transaction_id"))
print(a.get("poop",0))

a[object()] = 123

print(a)

a[object()] = 234

print(a)

print(list(a.values()))

print(str(1001))
print(str("1001"))