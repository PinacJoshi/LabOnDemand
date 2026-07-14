# Lab On Demand: Scenario Configuration & Architecture Blueprint

Welcome to the definitive configuration and architectural guide for **Lab On Demand** (`labod`). This documentation details how to construct, customize, and deploy multi-homed, completely isolated cybersecurity lab environments using a single declarative YAML profile.

## 1. Architectural Architecture & Core Foundations

The control plane orchestrates local Docker resources by abstracting low-level container networks and image layering states into clean configurations. To maximize lab utility while ensuring structural stability, the orchestrator adheres to three core design concepts:

### A. Global Labeling & Teardown Profiles

Every asset provisioned by the platform (networks, standard containers, custom workspaces, and temporary image layers) is stamped with metadata labels defined in `config.py`.

These labels include `managed_by=labod` and `scenario=<scenario_slug>` (where the slugified name is generated via `scenario_name.lower().replace(" ", "_")`).

There are two teardown option, each mode is offered in decommission of both running scenario and to delete dynamically created docker images.

* **Targetted Decommission Mode (`labod (decommission/decommission-images) <config_path>`)**: Parses the target YAML file to compute the specific `scenario_slug` and drops matching containers, networks, and custom images.


* **Global Decommission Mode (`labod (decommission/decommission-images)`)**: Bypasses local configuration files entirely. It queries the active Docker daemon and issues a global engine filter sweep matching `managed_by=labod` to wipe all active assets instantly, ensuring zero persistent disk or memory leakage.



### B. Multi-Homing Network Mechanics

Docker natively restricts network attachment to a single interface during container creation.

The container is initialized strictly attached to the first network listed in the node configuration (`assigned_nets[0]`). Once the container is running, the engine slices the remaining array (`assigned_nets[1:]`) and loops through each secondary network object, programmatically executing a downstream `.connect(container)` hook.

This binds multiple independent interfaces to a single runtime environment with dedicated IP addresses inside each subnet.



### C. In-Memory Image Compilation

To eliminate namespace collisions across concurrent training sessions, custom images compiled via `build_modifiers` are tagged using a scoped naming schema: `labod/<scenario_slug>-<node_name>`.

---

## 2. Complete YAML Schema Specification

The entire lifecycle of a lab scenario is governed by a single YAML file. Below is the comprehensive data definition for every key and option supported by the parsing engine.

### A. Top-Level Elements

| Key | Data Type | Requirement | Range / Permitted Values | Functional Impact |
| --- | --- | --- | --- | --- |
| `scenario` | `String` | Optional (Defaults to `unnamed_scenario` + `random int`. Targetted Decommision won't work if scenarion name not provided) | Alphanumeric, spaces, underscores, hyphens | Defines the baseline identifier for the lab environment. Transformed into a lowercase snake_case token (`scenario_slug`) to tag and isolate all network namespaces and container clusters. |
| `networks` | `List[Block]` | Required | A list containing individual network definition blocks | Declares the custom isolated virtual subnets that form the topology of the training range.|
| `nodes` | `List[Block]` | Optional | A list containing individual infrastructure/victim node blocks | Defines standard servers, target environments, misconfigured hosts, or secondary assets within the range.|
| `defender_workspace` | `Block` | Optional | A single specialized node structure | Spins up the interactive visual workstation for analysts.|
| `attacker_node` | `Block` | Optional | A single specialized node structure | Deploys an offensive emulation system, automatically delayed during launch sequences to ensure victim systems have completed initialization.|
| `instructions` | `String` | Optional | Multi-line string (Markdown) | A customized instructions markdown blob printed to the terminal after provisioning is complete. You can use |

---

### B. Network Definition Block (`networks`)

| Key | Data Type | Requirement | Range / Permitted Values | Default Value | Functional Impact |
| --- | --- | --- | --- | --- | --- |
| `name` | `String` | Required | Unique alphanumeric identifier (no spaces) | N/A | The local identifier used by nodes to reference this subnet, appended to the scenario slug to form the true system network name: `{scenario_slug}_network_{name}`. |
| `driver` | `String` | Optional | `"bridge"`, `"overlay"`, `"macvlan"` | `"bridge"` | Specifies the Docker network subsystem backing the topology. |
| `internal` | `Boolean` | Optional | `true` or `false` | `false` | When set to `true`, completely disconnects the network from the host's default external gateway, blocking ingress/egress internet traffic to isolate toxic or offline exercises. |

> **VNC Network Recommendation:** To ensure the VNC stream works properly, you must create a dedicated network for the `defender_workspace` that allows it to communicate with the host's browser. It is strongly recommended to name this network `vnc_host_bridge` and it **must NOT** be internal (`internal: false`).

---

### C. Node Core Definition Block

These configuration choices apply uniformly across standard infrastructure nodes, defender workspaces, and attacker machines. Except for `build_modifiers`, which is only used for defender workspaces.

| Key | Data Type | Requirement | Range / Permitted Values | Default Value | Functional Impact |
| --- | --- | --- | --- | --- | --- |
| `name` | `String` | Required | Unique alphanumeric string per scenario | N/A | Sets the container name suffix. Evaluated internally as `{scenario_slug}_{name}`. |
| `base_image` | `String` | Required | Valid Docker Hub or private registry image | N/A | Points to the root filesystem template for the container. Triggering supported images prefixed with `pinacjoshi/labod` unlocks native dynamic tool tracking and advanced file hooks. |
| `networks` | `List[String]` | Required | Must reference names declared in the `networks` root key | N/A | Binds the host to specific subnets. Listing multiple entries triggers the sequential multi-homing engine loop (`assigned_nets[1:]`). |
| `mem_limit` | `String` | Optional | Positive integer followed by `m` or `g` | `"1g"` | Strict blast-radius memory ceiling preventing individual systems from exhausting host hardware. |
| `cpus` | `Float` | Optional | `0.1` to maximum available host logic cores | `1.0` | Defines fractional CPU allocations. Converted to nano-CPUs (`int(cpus * 1e9)`) to throttle processing speed. |
| `exec_command` | `String` | Optional | Valid Linux shell script / command sequence | N/A | Forces execution of a persistent process or routine upon container boot. Evaluated safely inside `["/bin/sh", "-c", exec_command]`. |
| `cap_add` | `List[String]` | Optional | Valid Linux Capabilities | `[]` | Grants advanced kernel execution privileges to the container space. |
| `cap_drop` | `List[String]` | Optional | Valid Linux Capabilities | `[]` | Strips standard container permissions to model hardened environments or enforce restriction constraints. |
| `volumes` | `List[String]` | Optional | Host/Container absolute paths or relative syntax | `[]` | Mounts local file directories into the container. Relative declarations starting with `.` are automatically resolved to raw absolute paths before execution. |
| `build_modifiers` | `Block / List` | Optional | Conditional based on `base_image` | N/A | Instructs the custom made defender workspace image framework to compile a unique, scenario-specific image variant in memory before running. |

---

#### Detailed Anatomy of `build_modifiers`

The internal structure of `build_modifiers` adapts automatically depending on whether the system detects a custom platform image or a generic baseline.

**Scenario A: Supported Project Suite (Contains `pinacjoshi/labod`)**

Expects a structured dictionary with dedicated configuration arrays:
* `install_packages` (`List[String]`): Standard software packages to be fetched via native package managers.


* `raw_instructions` (`List[String]`): Raw Dockerfile instruction strings (e.g., `["ENV VAR=VALUE"]`) appended directly onto the dynamic assembly stream.


* `mkdir` (`List[String]`): A list of raw strings representing directory paths to create at build time (e.g., `["/config/secret_data", "/config/logs"]`).


* `mkfile` (`List[Dict]`): A list of dictionary objects defining a `path` and `data` key to generate inline files (e.g., seeding a custom flag or text file).


**Scenario B: Generic Base Images (e.g., `ubuntu:latest`, `alpine:3.19`)**


Expects a flat, sequential list of raw Dockerfile string commands (`List[String]`). Providing a dictionary modifier structure on a generic image will prompt the orchestrator to throw a warning and skip modifications to avoid broken dependencies.

---

## 3. The Custom Defender Workspace

The foundational pillar for the security analyst's interactive experience is the custom workspace image.

### A. Core OS and Presentation Stack

* **Base Framework Layer**: Built directly on top of `ghcr.io/linuxserver/baseimage-kasmvnc:ubuntunoble`. This base image couples an ultra-stable Ubuntu Noble base with KasmVNC—a highly efficient web-based remote display engine that converts local X-server visuals into a high-speed HTTP transport stream over port `3000`.


* **Zero-Authentication Design**: Tailored for frictionless laboratory accessibility. Students avoid tedious login panels; pointing a browser at the allocated host workspace port drops them directly into a graphical environment.


* **Desktop Environment**: XFCE 4 is chosen specifically for its light resource footprint and modular panel structure, initialized cleanly using a dedicated startup controller script located at `/defaults/autostart`.


### B. Workspace Paths and Permissions

* **Unified Path Enforcement**: The image shifts all runtime paths, variable frames, configuration settings, and desktop configurations into `/config`.


* **User Context Mapping**: The environment operates under user profile `abc` (statically mapped to UID `1000` / GID `1000`). A finalization hook executes `chown -R 1000:1000 /config`, keeping all desktop environments write-accessible.



### C. Pre-Installed SOTA Security Toolset

The baseline image is shipped production-ready with the following tools pre-compiled into its layers:

* **Networking & Packet Analysis**: `wireshark` (configured with raw packet injection capability via `install-setuid true`), `tshark`, `tcpdump`, `nmap`, `iproute2`, `iputils-ping`, and `net-tools`.


* **Malware Analysis & Forensics**: `yara`, `jq`, `binutils`, `binwalk`, `strace`, `libimage-exiftool-perl`, and `xxd`.


* **Productivity & OS Utilities**: Native `firefox`, `tmux`, and `python3-pip`.



### D. The Dynamic Tool Manifest Tracking Engine

* **Static Validation Check**: Upon logging into the desktop, `/defaults/autostart` pops open an explicit `xfce4-terminal` that executes a custom splash screen, verifying the core tool loadout and dynamically installed packages.


* **Dynamic Expansion**: When a scenario configuration leverages `build_modifiers.install_packages`, the provisioner runs the installation and logs the package names directly into `/etc/labod_custom_tools.txt`.


* **Splash Integration**: The splash script scans this manifest file and prints dynamically added tools under a dedicated purple tracking header `[+] Scenario-Specific Tools`.

---

# Example Yaml Config

```yaml
# =============================================================================
# Lab On Demand (labod) - Scenario Blueprint
# Theme: SOC Analyst Triage & Lateral Movement Detection
# =============================================================================

# The scenario token is parsed by the Python orchestrator into a slugified 
# format (e.g., soc_analyst_triage) to isolate namespaces and tag all created
# Docker assets with the global metadata label: managed_by=labod
scenario: "SOC Analyst Triage"

networks:
  # MANDATORY: The primary bridge allowing KasmVNC to stream the desktop UI 
  # via port 8080 to the native host browser. Must strictly remain internal: false.
  - name: "vnc_host_bridge"
    driver: "bridge"
    internal: false 
    
  # Isolated layer-2 domain where the compromised assets reside. 
  # Setting internal: true prevents internet egress, protecting the host.
  - name: "dmz_network"
    driver: "bridge"
    internal: true

nodes:
  # Victim Node 1: Simulating a legacy headless environment
  - name: "legacy_server"
    base_image: "debian:13"
    mem_limit: "1g"
    networks: 
      - "dmz_network"
    # For generic base images, build_modifiers expects a flat array of Dockerfile syntax.
    # Notice the APT cache volatility optimization: chained updates and immediate cleanup.
    build_modifiers:
      - "RUN apt-get update && apt-get install -y nginx && rm -rf /var/lib/apt/lists/*"
    exec_command: "nginx -g 'daemon off;'"

  # Victim Node 2: Lightweight service node
  - name: "telemetry_node"
    base_image: "alpine:latest"
    mem_limit: "512m"
    networks: 
      - "dmz_network"
    build_modifiers:
      - "RUN apk add --no-cache curl iperf3"
    exec_command: "iperf3 -s"

defender_workspace:
  name: "analyst_desktop"
  base_image: "pinacjoshi/labod-defender-base:latest"
  exposed_port: 8080
  networks: 
    # Multi-Homing Engine Execution: 
    # assigned_nets[0] -> vnc_host_bridge (Instantiated at container boot for UI streaming)
    # assigned_nets[1:] -> dmz_network (Dynamically connected via the engine's downstream loop)
    - "vnc_host_bridge" 
    - "dmz_network"
  # Because we are using the supported base image, we unlock the dictionary schema
  build_modifiers:
    install_packages:
      - "suricata"
      - "zeek"
    mkdir: 
      - "/config/evidence_vault"
      - "/config/scripts"
    mkfile: 
      - path: "/config/scripts/noterm_setup.sh"
        data: |
          #!/bin/bash
          echo "Initializing Noterm TUI environment..."
      - path: "/config/evidence_vault/syslog_extract.log"
        data: "Failed password for root from 192.168.1.50 port 54322 ssh2"
    raw_instructions:
      - "ENV EXERCISE_PHASE='Triage'"

attacker_node:
  name: "threat_actor"
  base_image: "alpine:latest"
  networks: 
    - "dmz_network"
  build_modifiers:
    - "RUN apk add --no-cache nmap curl"
  # The control plane automatically delays attacker_node execution by 5 seconds
  # to ensure legacy_server and telemetry_node are fully listening.
  exec_command: |
    sleep 10 && nmap -sV legacy_server

# The CLI outputs this markdown blob dynamically after the provisioning sequence completes.
instructions: |
  # Exercise Initialization Complete
  
  Welcome to the SOC Analyst Triage scenario. Your interactive workspace is now streaming at `http://127.0.0.1:8080`.
  
  **Environment Targets:**
  * **Legacy Server (Debian 13):** Assigned IP `{legacy_server[ip]}`
  * **Telemetry Node:** Assigned IP `{telemetry_node[ip]}`
  
  **Primary Objectives:**
  1. Inspect the pre-seeded logs located at `/config/evidence_vault/syslog_extract.log`.
  2. Monitor `dmz_network` traffic for active scanning originating from the attacker node.
```