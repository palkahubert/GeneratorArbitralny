import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("awg_output.csv")
x = df["sd_out"].astype(float)

alpha = 0.04
y = []
prev = 0.0
for v in x:
    prev = prev + alpha * (v - prev)
    y.append(prev)

plt.figure(figsize=(10, 4))
plt.plot(df["raw_sample"] / 65535.0, label="raw sample")
plt.plot(df["scaled_sample"] / 65535.0, label="scaled sample")
plt.title("Unsigned LUT samples and scaled samples")
plt.xlabel("n")
plt.ylabel("level")
plt.grid(True)
plt.legend()
plt.tight_layout()

plt.figure(figsize=(10, 3))
plt.plot(x.iloc[:300])
plt.title("1-bit sigma-delta stream fragment")
plt.xlabel("n")
plt.ylabel("PDM")
plt.grid(True)
plt.tight_layout()

plt.figure(figsize=(10, 4))
plt.plot(df["scaled_sample"] / 65535.0, label="scaled sample")
plt.plot(y, label="PDM after simple LPF", alpha=0.8)
plt.title("Sample before sigma-delta vs LPF output")
plt.xlabel("n")
plt.ylabel("level")
plt.grid(True)
plt.legend()
plt.tight_layout()

plt.show()
