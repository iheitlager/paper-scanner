import time

with open("progress.txt", "w") as f:
    for i in range(1, 4):
        f.write(f"Step {i} completed\n")
        # f.flush()  # Write to file immediately
        print(f"Step {i} completed", flush=True)  # Console output
        time.sleep(1)  # Simulate delay

for i in range(1, 4):
    with open("progress.txt", "w+") as f:
        f.write(f"Step {i} completed\n")
        print(f"Step {i} completed", flush=True)  # Console output
        time.sleep(1)  # Simulate delay