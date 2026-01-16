
with open(r"c:\temp\Magic\Github\Hack Market\market-hacking\app.py", 'rb') as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        if 2375 <= i+1 <= 2385:
            print(f"Line {i+1}: {line.hex()}")
