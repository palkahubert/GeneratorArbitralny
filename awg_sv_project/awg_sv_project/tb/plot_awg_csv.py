import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("awg_output.csv")
x = 2 * df["sd_out"].astype(float) - 1

alpha = 0.04
y = []
prev = 0.0
for v in x:
    prev = prev + alpha * (v - prev)
    y.append(prev)

plt.figure(figsize=(10, 4))
plt.plot(df["raw_sample"] / 32768.0, label="raw sample")
plt.plot(df["scaled_sample"] / 32768.0, label="scaled sample")
plt.title("Probki z LUT i po skalowaniu")
plt.xlabel("n")
plt.ylabel("amplituda")
plt.grid(True)
plt.legend()
plt.tight_layout()

plt.figure(figsize=(10, 3))
plt.plot(x.iloc[:300])
plt.title("Fragment strumienia 1-bit sigma-delta")
plt.xlabel("n")
plt.ylabel("PDM")
plt.grid(True)
plt.tight_layout()

plt.figure(figsize=(10, 4))
plt.plot(df["scaled_sample"] / 32768.0, label="scaled sample")
plt.plot(y, label="PDM po prostym LPF", alpha=0.8)
plt.title("Porownanie probki przed sigma-delta i sygnalu po LPF")
plt.xlabel("n")
plt.ylabel("amplituda")
plt.grid(True)
plt.legend()
plt.tight_layout()

plt.show()
