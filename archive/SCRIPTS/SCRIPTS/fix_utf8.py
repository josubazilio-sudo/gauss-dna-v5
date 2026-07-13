import re

with open('ENGINE/scanner/scanner_signal.py', 'rb') as f:
    raw = f.read()

# Pattern: \xc3\x83\xc2\x?? should become \xc3\x??
# where ?? is the same byte
fixed = bytearray()
i = 0
count = 0
while i < len(raw):
    if (i + 3 < len(raw) and
        raw[i] == 0xc3 and raw[i+1] == 0x83 and
        raw[i+2] == 0xc2):
        # Double-encoded: skip the \x83\xc2, keep \xc3 + next byte
        fixed.append(0xc3)
        fixed.append(raw[i+3])
        i += 4
        count += 1
    else:
        fixed.append(raw[i])
        i += 1

with open('ENGINE/scanner/scanner_signal.py', 'wb') as f:
    f.write(bytes(fixed))

# Verify
with open('ENGINE/scanner/scanner_signal.py', 'rb') as f:
    verify = f.read()

# Check for remaining double-encoding
remaining = 0
i = 0
while i < len(verify) - 3:
    if verify[i] == 0xc3 and verify[i+1] == 0x83 and verify[i+2] == 0xc2:
        remaining += 1
        i += 1
    else:
        i += 1

print(f"Fixed: {count} double-encoded sequences")
print(f"Remaining: {remaining}")

# Test that the file is valid UTF-8
try:
    text = verify.decode('utf-8')
    print(f"Valid UTF-8: yes ({len(text)} chars)")
except Exception as e:
    print(f"Valid UTF-8: NO — {e}")

# Show corrected strings
for i, line in enumerate(text.split('\n'), 1):
    if 'Tendência' in line or 'Confiança' in line or 'Direção' in line:
        print(f"  L{i}: ...{line.strip()[:80]}...")
