# EDSim

**An LLM-powered multi-agent simulation of emergency department operations.**

[![CI](https://github.com/denoslab/EDSim/actions/workflows/ci.yml/badge.svg)](https://github.com/denoslab/EDSim/actions/workflows/ci.yml)
[![Docker](https://github.com/denoslab/EDSim/actions/workflows/docker.yml/badge.svg)](https://github.com/denoslab/EDSim/actions/workflows/docker.yml)

EDSim builds on the [Generative Agents](https://arxiv.org/abs/2304.03442) framework. Four agent types — Doctor, Bedside Nurse, Triage Nurse, and Patient — perceive their environment, plan actions, converse with each other, and execute behaviours driven by LLM calls.

## Components

| Component | Description |
|---|---|
| **Simulation engine** (`reverie/`) | Core backend that drives agent cognition and state |
| **Legacy frontend** (`environment/frontend_server/`) | Django + Phaser tile-based viewer |
| **3D Floor Plan Viewer** (`environment/react_frontend/`) | React + Three.js interactive 3D renderer (Phase 1) |
| **Analysis pipeline** (`analysis/`) | Post-simulation metrics computation |

## Quick start

```bash
# Docker (recommended)
cp .env.example .env && docker compose up --build

# 3D Floor Plan Viewer (standalone)
./run_map_viewer.sh    # http://127.0.0.1:5173
```

## Links

- [GitHub repository](https://github.com/denoslab/EDSim)
- [Preprint (Research Square)](https://www.researchsquare.com/article/rs-8960989/v1)
