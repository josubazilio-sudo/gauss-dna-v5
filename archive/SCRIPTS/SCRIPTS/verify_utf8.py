with open('ENGINE/scanner/scanner_signal.py', 'rb') as f:
    raw = f.read()

# Show bytes around "Tend" 
idx = raw.find(b'Tend')
print(f"'Tend' at offset {idx}")
chunk = raw[idx:idx+20]
print(f"Bytes: {chunk.hex()}")
print(f"UTF-8: {chunk.decode('utf-8')!r}")

# Show bytes around "Confian"
idx2 = raw.find(b'Confian')
print(f"\n'Confian' at offset {idx2}")
chunk2 = raw[idx2:idx2+20]
print(f"Bytes: {chunk2.hex()}")
print(f"UTF-8: {chunk2.decode('utf-8')!r}")

# Show bytes around "Dire"
idx3 = raw.find(b'Dire')
print(f"\n'Dire' at offset {idx3}")
chunk3 = raw[idx3:idx3+20]
print(f"Bytes: {chunk3.hex()}")
print(f"UTF-8: {chunk3.decode('utf-8')!r}")

# Check for any remaining \xc3\x83\xc2 sequences
remaining = 0
for i in range(len(raw)-3):
    if raw[i] == 0xc3 and raw[i+1] == 0x83 and raw[i+2] == 0xc2:
        remaining += 1
print(f"\nRemaining double-encoded: {remaining}")
