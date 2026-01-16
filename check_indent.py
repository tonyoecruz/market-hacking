
with open(r"c:\temp\Magic\Github\Hack Market\market-hacking\app.py", 'rb') as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        if 2360 <= i+1 <= 2400:
            prefix = line[:30]
            print(f"Line {i+1}: {repr(prefix)}")
