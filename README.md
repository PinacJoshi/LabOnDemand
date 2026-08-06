# Lab on Demand (labod)

An automated, CLI-driven cybersecurity training range framework designed to provision, manage, and destroy complex, multi-homed lab networks and victim topologies on demand.

With **Lab On Demand**, you can instantly deploy isolated, multi-node lab networks and stream an interactive, fully-loaded analyst workstation directly to your native web browser over HTTP, requiring **zero local configuration**, **zero password panels**, and maintaining absolute network isolation.



## 🚀 Key Features

* **Instant GUI over HTTP:** Defender Workstation containers run a resource friendly XFCE4 desktop streamed in plaintext via **KasmVNC** over port default port `8080` for seamless, browser based analyst access with no login barriers.
* **Deterministic Isolation:** Dynamic image builds are scoped directly to the active scenario slug (`labod/{scenario_slug}-{node_name}:latest`) to guarantee parallel lab run collision prevention.
* **Complex Multi-Homing Network Slicing:** Provisions complex multi-homed topologies dynamically by instantiating nodes on a primary network interface and hot plugging subsequent networks sequentially via the Python Docker SDK.
* **Dual-Mode Teardown Safety:** Support for targeted surgical teardowns (de-provisioning specific YAML scenarios) as well as global teardown routines using strict Docker metadata sweeps filtered by global identifier label (`managed_by=labod`).


## 🛠️ Tech Stack

* **Control Plane:** Python 3.14+
* **Package & Virtual Environment Management:** [uv](https://github.com/astral-sh/uv)
* **CLI Framework:** Click
* **Container Orchestration:** Python Docker SDK
* **Streaming Base Image:** [`pinacjoshi/labod-defender-base:latest`](https://hub.docker.com/r/pinacjoshi/labod-defender-base) 


## 📋 Prerequisites

Before deploying lab environments, ensure you have the following installed on your system:

1. **Docker Engine / Desktop:** Must be running locally and accessible without `sudo` (configured in the local `docker` group).
2. **uv:** Astral's lightning-fast Python package and project manager. Goto [Astral - uv](https://docs.astral.sh/uv/getting-started/installation/#installation-methods) website and follow the instructions to install it. You can also use your native package manager to install it.
3. **Python**: Version 3.14+



## ⚙️ Installation & Setup

Because this project utilizes `uv` to orchestrate Python runtimes and lockfiles natively, setting up your environment requires a single step:

1. Clone this repository and navigate to its root:
```bash
git clone https://github.com/PinacJoshi/LabOnDemand.git
cd LabOnDemand
```

2. Sync the project dependencies and establish your local virtual environment:
```bash
uv sync
```

The `uv sync` command reads `pyproject.toml` and `uv.lock` to automatically assemble a locked, optimized virtual environment containing the exact required versions of `click`, `docker`, and `pyyaml`.


## 📖 Basic Usage

All execution vectors route through the CLI manager inside `main.py`. Wrap execution commands with `uv run` to guarantee they run inside the context of your managed virtual environment.

### 1. Deploy a Lab Scenario

To compile dynamic image layers, map network bridges, and spin up an active lab topology:

```bash
uv run main.py deploy scenarios/your_scenario.yaml
```

### 2. Teardown & Clean Up

The system tracks all allocated resources (networks, containers, volume endpoints) using custom Docker labels to ensure no stale network resources clog your host interface engine. Teardowns are managed via two modes:

#### A. Targetted Teardown Mode (Specific Scenario)

To selectively target and dismantle only the assets created by a specific scenario file:

```bash
uv run main.py decommission scenarios/your_scenario.yaml
```

#### B. Global Teardown Mode (Sweep All Labs)

To forcefully purge all active lab containers and networks managed by the builder across the entire system without needing the original YAML configuration files:

```bash
uv run main.py decommission
```

> ⚠️ **Note:** This command triggers an interactive click-confirmation prompt before executing a system-wide metadata label sweep filtering on `managed_by=labod`.

---

## 📝 Customizing Scenarios

All scenario structures, subnets, custom image layers, and machine configurations are declared inside standard YAML formats.

To learn how to design, customize, or modify scenario deployment manifests, please consult the dedicated documentation file present in the repo:

👉 **[yamlconfig_README.md](https://github.com/PinacJoshi/LabOnDemand/blob/main/yamlconfig_README.md)**

---

## 📂 Project Structure

```text
├── data/                 # Shared data mount points and capture volumes
├── scenarios/            # Ready-to-use scenario YAML files
├── src/                  # Core Python modules (orchestration engine, helpers)
├── config.py             # Global configuration paths and variables
├── main.py               # CLI entrypoint (Click commands interface)
├── pyproject.toml        # Declarative uv project specifications
├── uv.lock               # Strictly locked package dependency tree
└── yamlconfig_README.md  # Detailed schema documentation for scenarios
```


## Current Development
- Make more scenario yaml configs