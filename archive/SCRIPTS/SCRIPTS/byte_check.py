import sys

# Check scanner_types.py for UTF-8 corruption too
for fname in ['ENGINE/scanner/scanner_signal.py', 'ENGINE/scanner/scanner_types.py']:
    with open(fname, 'rb') as f:
        raw = f.read()
    
    # Count double-encoded sequences
    double_encoded = 0
    i = 0
    while i < len(raw) - 1:
        # Look for \xc3\x83\xc2\xaa pattern (Ãª) or similar double-encoding
        if raw[i] == 0xc3 and raw[i+1] >= 0x80:
            # This is a valid UTF-8 2-byte sequence
            if i+2 < len(raw) and raw[i+1] == 0x83 and raw[i+2] == 0xc2:
                double_encoded += 1
        i += 1
    
    decoded = raw.decode('utf-8', errors='replace')
    
    # Find all non-ASCII chars
    issues = 0
    for i, c in enumerate(decoded):
        if ord(c) > 127:
            if c == '\ufffd':
                issues += 1
    
    print(f'{fname}:')
    print(f'  Size: {len(raw)} bytes')
    print(f'  Double-encoded sequences: {double_encoded}')
    print(f'  Replacement chars (U+FFFD): {issues}')
    print()

# Specific check: the known corrupted strings
with open('ENGINE/scanner/scanner_signal.py', 'rb') as f:
    raw = f.read()

# Search for specific patterns
for term in [b'Tend\xc3\x83\xc2\xaa', b'Tend\xc3\xaa']:
    idx = raw.find(term)
    if idx >= 0:
        print(f'Found {term.hex()} at offset {idx}')
    else:
        print(f'NOT found: {term.hex()}')

# Show actual string on each corrupted line
decoded = raw.decode('utf-8', errors='replace')
for i, line in enumerate(decoded.split('\n'), 1):
    if any(ord(c) > 127 for c in line):
        # Show bytes of non-ASCII section
        for c in line:
            if ord(c) > 127:
                print(f'  L{i}: char U+{ord(c):04X} ({c!r}) in: ...{line[max(0,line.index(c)-5):line.index(c)+10]}...')
                break
