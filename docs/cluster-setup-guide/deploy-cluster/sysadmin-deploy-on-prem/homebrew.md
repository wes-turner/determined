(install-using-homebrew)=

# Install Determined Using Homebrew (macOS)

Determined publishes a Homebrew tap for installing the Determined master and agent as Homebrew
services on macOS, for both Apple silicon and Intel hardware.

While it is most common to install the master and agent on the same machine, it is also possible to
install the master and agent on separate nodes, or install agents on multiple machines and connect
them to one master.

:::{note}
Due to the limitations of Docker networking on macOS, distributed training across multiple macOS
agents is not supported.
:::

## Installation - Master

1. Add Homebrew tap.

   ```
   brew tap determined-ai/determined
   ```

2. Install `determined-master` package. Determined uses a PostgreSQL database to store metadata,
   and `postgresql@14` will be pulled in as a dependency.

   ```
   brew install determined-master
   ```

3. Start the PostgreSQL server, and set up a database and default user.

   ```
   brew services start postgresql@14
   createuser postgres
   createdb determined
   ```

4. Start the Determined master service.

   ```
   brew services start determined-master
   ```

5. If needed, you can configure the master by editing `/usr/local/etc/determined/master.yaml` and
   restarting the service.

## Installation - Agent

1. The Determined agent uses Docker to run your workloads. For more information, visit {ref}`Docker
   for Mac installation instructions <install-docker-on-macos>`.

2. By default, Determined will store checkpoints in `$(brew --prefix)/var/determined/data`, which
   is typically `/usr/local/var/determined/data` or `/opt/homebrew/var/determined/data`. Make
   sure to configure it as a shared path for Docker for Mac in Docker -> Preferences... -> Resources
   -> File Sharing.

3. When installing on a different machine than the master, add Homebrew tap.

   ```
   brew tap determined-ai/determined
   ```

4. Install `determined-agent` package.

   ```
   brew install determined-agent
   ```

5. When installing on a different machine than the master, edit
   `/usr/local/etc/determined/agent.yaml` and change `master_host` and `container_master_host`
   to your master network hostname, and `master_port` to your master network port.

6. Start the `determined-agent` service.

   ```
   brew services start determined-agent
   ```
