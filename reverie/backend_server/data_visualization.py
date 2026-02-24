"""
Script to visualize patient wait times, treatment times, and ED times in the ED by CTAS level,
with arrow-key navigation (One figure per stage: VisitPIA → DispPIA → PiaLeave).

*** MAKE SURE TO USE ARROW KEYS TO NAVIGATE THROUGH THE FIGURES ***
"""

import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv('../../environment/frontend_server/storage/test-simulation/reverie/state_times.csv')

# Data for Waiting
waiting_cols = ["WAITING_FOR_TRIAGE", "TRIAGE", "WAITING_FOR_NURSE", "WAITING_FOR_FIRST_ASSESSMENT"]
df[waiting_cols] = df[waiting_cols] / 60.0
wait_times = df.melt(id_vars=["CTAS"], value_vars=waiting_cols, var_name="WaitType", value_name="WaitTime").dropna(subset=["WaitTime"])

# Data for Treatment
treatment_cols = ["WAITING_FOR_TEST", "GOING_FOR_TEST", "WAITING_FOR_RESULT"]
df[treatment_cols] = df[treatment_cols] / 60.0
treatment_times = df.melt(id_vars=["CTAS"], value_vars=treatment_cols, var_name="TreatmentType", value_name="TreatmentTime").dropna(subset=["TreatmentTime"])

# Data for ED
ED_cols = ["WAITING_FOR_DOCTOR", "LEAVING"]
df[ED_cols] = df[ED_cols] / 60.0
ED_times = df.melt(id_vars=["CTAS"], value_vars=ED_cols, var_name="EDWaitType", value_name="EDTime").dropna(subset=["EDTime"])

# Plot Waiting Times
def plot_waiting(fig):
    fig.clf()
    waiting_ctas_levels = sorted(wait_times["CTAS"].dropna().unique())
    axes = fig.subplots(1, len(waiting_ctas_levels))
    if len(waiting_ctas_levels) == 1:
        axes = [axes]

    max_count = 0
    hists = []
    for a, ctas in zip(axes, waiting_ctas_levels):
        subset = wait_times[wait_times["CTAS"] == ctas]["WaitTime"]
        counts, bins, patches = a.hist(subset, bins=20, edgecolor="black")
        hists.append((counts, a))
        max_count = max(max_count, counts.max())
        a.set_title(f"VisitPia CTAS {int(ctas)}")
        a.set_xlabel("Wait Times (Hours)")
        a.set_ylabel("Frequency")

    # Adds some extra space at the top
    ylim_max = int(max_count * 1.1)
    for _, ax in hists:
        ax.set_ylim(0, ylim_max)

    fig.suptitle("")
    fig.tight_layout()

# Plot Treatment Times
def plot_treatment(fig):
    fig.clf()
    treatment_ctas_levels = sorted(treatment_times["CTAS"].dropna().unique())
    axes = fig.subplots(1, len(treatment_ctas_levels))
    if len(treatment_ctas_levels) == 1:
        axes = [axes]

    max_count = 0
    hists = []
    for a, ctas in zip(axes, treatment_ctas_levels):
        subset = treatment_times[treatment_times["CTAS"] == ctas]["TreatmentTime"]
        counts, bins, patches = a.hist(subset, bins=20, edgecolor="black")
        hists.append((counts, a))
        max_count = max(max_count, counts.max())
        a.set_title(f"DispPia CTAS {int(ctas)}")
        a.set_xlabel("Wait Times (Hours)")
        a.set_ylabel("Frequency")

    # Adds some extra space at the top
    ylim_max = int(max_count * 1.1)
    for _, ax in hists:
        ax.set_ylim(0, ylim_max)

    fig.suptitle("")
    fig.tight_layout()

# Plot ED Times
def plot_ED(fig):
    fig.clf()
    ctas_levels = sorted(ED_times["CTAS"].dropna().unique())
    axes = fig.subplots(1, len(ctas_levels))
    if len(ctas_levels) == 1:
        axes = [axes]

    max_count = 0
    hists = []
    for a, ctas in zip(axes, ctas_levels):
        subset = ED_times[ED_times["CTAS"] == ctas]["EDTime"]
        counts, bins, patches = a.hist(subset, bins=20, edgecolor="black")
        hists.append((counts, a))
        max_count = max(max_count, counts.max())
        a.set_title(f"PiaLeave CTAS {int(ctas)}")
        a.set_xlabel("Wait Times (Hours)")
        a.set_ylabel("Frequency")

    # Adds some extra space at the top
    ylim_max = int(max_count * 1.1)
    for _, ax in hists:
        ax.set_ylim(0, ylim_max)

    fig.suptitle("")
    fig.tight_layout()

# Slides
slides = [plot_waiting, plot_treatment, plot_ED]
current_idx = [0]

fig = plt.figure(figsize=(12, 5))

def draw():
    slides[current_idx[0]](fig)
    fig.suptitle("")
    fig.canvas.draw_idle()

# Keyboard Navigation
def on_key(event):
    if event.key == "right":
        current_idx[0] = (current_idx[0] + 1) % len(slides)
        draw()
    elif event.key == "left":
        current_idx[0] = (current_idx[0] - 1) % len(slides)
        draw()

fig.canvas.mpl_connect("key_press_event", on_key)

draw()
plt.show()