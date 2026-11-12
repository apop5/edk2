# @file LinuxGccToolChain.py
# Plugin to configures paths for GCC AARCH64/RISCV/LOONGARCH64 Toolchain
##
# This plugin sets environment variables used in tools_def.template to specify the GCC compiler
# for the requested build architecture.
# Reports compiler and linker paths and versions through the version aggregator.
#
# Copyright (c) Microsoft Corporation
# Copyright (c) 2020, Hewlett Packard Enterprise Development LP. All rights reserved.<BR>
# Copyright (c) 2022, Loongson Technology Corporation Limited. All rights reserved.<BR>
# SPDX-License-Identifier: BSD-2-Clause-Patent
##
import os
import logging
import shutil
from io import StringIO
from edk2toolext.environment.plugintypes.uefi_build_plugin import IUefiBuildPlugin
from edk2toolext.environment import shell_environment, version_aggregator
from edk2toollib.utility_functions import RunCmd


class LinuxGccToolChain(IUefiBuildPlugin):

    def do_post_build(self, thebuilder):
        """Return success without performing any post-build actions.

        Args:
            thebuilder: Build instance supplied by the plugin framework.

        Returns:
            Zero.
        """
        return 0

    def do_pre_build(self, thebuilder):
        """Configure GCC toolchains and report compiler and linker versions.

        Args:
            thebuilder: Build instance providing the toolchain tag and target
                architectures.

        Returns:
            Zero on success or for other toolchain tags, or the nonzero status
            from a failed toolchain check.
        """
        self.Logger = logging.getLogger("LinuxGccToolChain")

        #
        # GCC - The only remaining supported GCC toolchain is now "GCC", others have been deprecated then removed.
        #
        if thebuilder.env.GetValue("TOOL_CHAIN_TAG") == "GCC":
            # Start with AAACH64 compiler
            if "AARCH64" in thebuilder.env.GetValue("TARGET_ARCH", "AARCH64"):
                ret = self._check_aarch64()
                if ret != 0:
                    self.Logger.critical("Failed in check aarch64")
                    return ret

            # Check RISCV64 compiler
            if "RISCV64" in thebuilder.env.GetValue("TARGET_ARCH", "RISCV64"):
                ret = self._check_riscv64()
                if ret != 0:
                    self.Logger.critical("Failed in check riscv64")
                    return ret

            # Check LoongArch64 compiler
            if "LOONGARCH64" in thebuilder.env.GetValue("TARGET_ARCH", "LOONGARCH64"):
                ret = self._check_loongarch64()
                if ret != 0:
                    self.Logger.critical("Failed in check loongarch64")
                    return ret

            env = shell_environment.GetEnvironment()
            for arch in thebuilder.env.GetValue("TARGET_ARCH", "").split():
                if arch in ("IA32", "X64"):
                    prefix = env.get_shell_var("GCC_BIN") or ""
                elif arch in ("AARCH64", "RISCV64", "LOONGARCH64"):
                    prefix = env.get_shell_var(f"GCC_{arch}_PREFIX") or ""
                else:
                    continue
                self._report_tool_version(f"GCC_{arch}", prefix + "gcc", "-dumpfullversion -dumpversion")
                self._report_tool_version(f"GNU_LD_{arch}", prefix + "ld", "--version")

        return 0

    def _report_tool_version(self, name, executable, arguments):
        """Report a tool's resolved path and first line of version output.

        Args:
            name: Version aggregator key, also used with the "_PATH" suffix.
            executable: Tool name or path to resolve.
            arguments: Command-line arguments used to query the version.

        Returns:
            None. Missing tools, failed commands, and empty output produce
            warnings without failing the build.
        """
        tool_path = shutil.which(executable)
        if tool_path is None:
            self.Logger.warning("Could not find %s for tool reporting", executable)
            return

        aggregator = version_aggregator.GetVersionAggregator()
        aggregator.ReportVersion(
            name + "_PATH", tool_path, version_aggregator.VersionTypes.INFO)
        with StringIO() as output:
            ret = RunCmd(f'"{tool_path}"', arguments, outstream=output)
            if ret != 0:
                self.Logger.warning("%s %s exited with code %d", tool_path, arguments, ret)
                return
            lines = output.getvalue().strip().splitlines()
        if not lines:
            self.Logger.warning("%s %s produced no output", tool_path, arguments)
            return
        aggregator.ReportVersion(name, lines[0].strip(), version_aggregator.VersionTypes.TOOL)

    def _check_aarch64(self):
        """Configure and validate the AARCH64 GCC prefix.

        Returns:
            Zero if the compiler exists or no prefix or install directory is
            configured, or -2 if the configured compiler does not exist.
        """
        # check to see if full path already configured
        if shell_environment.GetEnvironment().get_shell_var("GCC_AARCH64_PREFIX") is not None:
            self.Logger.info("GCC_AARCH64_PREFIX is already set.")

        else:
            # now check for install dir.  If set then set the Prefix
            install_path = shell_environment.GetEnvironment(
            ).get_shell_var("GCC_AARCH64_INSTALL")
            if install_path is None:
                return 0

            # make PREFIX to align with tools_def.txt
            prefix = os.path.join(install_path, "bin", "aarch64-none-linux-gnu-")
            shell_environment.GetEnvironment().set_shell_var("GCC_AARCH64_PREFIX", prefix)

        # now confirm it exists
        if not os.path.exists(shell_environment.GetEnvironment().get_shell_var("GCC_AARCH64_PREFIX") + "gcc"):
            self.Logger.error(
                "Path for GCC_AARCH64_PREFIX toolchain is invalid")
            return -2

        return 0

    def _check_riscv64(self):
        """Configure the RISCV64 GCC prefix and library search path.

        Returns:
            Zero if no install directory is configured or setup succeeds,
            or -2 if the configured compiler does not exist.
        """
        # now check for install dir.  If set then set the Prefix
        install_path = shell_environment.GetEnvironment(
        ).get_shell_var("GCC_RISCV64_INSTALL")
        if install_path is None:
            return 0

        # check to see if full path already configured
        if shell_environment.GetEnvironment().get_shell_var("GCC_RISCV64_PREFIX") is not None:
            self.Logger.info("GCC_RISCV64_PREFIX is already set.")

        else:
            # make PREFIX to align with tools_def.txt
            prefix = os.path.join(install_path, "bin", "riscv64-unknown-elf-")
            shell_environment.GetEnvironment().set_shell_var("GCC_RISCV64_PREFIX", prefix)

        # now confirm it exists
        if not os.path.exists(shell_environment.GetEnvironment().get_shell_var("GCC_RISCV64_PREFIX") + "gcc"):
            self.Logger.error(
                "Path for GCC_RISCV64_PREFIX toolchain is invalid")
            return -2

        # Check if LD_LIBRARY_PATH is set for the libraries of RISC-V GCC toolchain
        if shell_environment.GetEnvironment().get_shell_var("LD_LIBRARY_PATH") is not None:
            self.Logger.info("LD_LIBRARY_PATH is already set.")

        prefix = os.path.join(install_path, "lib")
        shell_environment.GetEnvironment().set_shell_var("LD_LIBRARY_PATH", prefix)

        return 0

    def _check_loongarch64(self):
        """Configure and validate the LoongArch64 GCC prefix.

        Returns:
            Zero if the compiler exists or no prefix or install directory is
            configured, or -2 if the configured compiler does not exist.
        """
        # check to see if full path already configured
        if shell_environment.GetEnvironment().get_shell_var("GCC_LOONGARCH64_PREFIX") is not None:
            self.Logger.info("GCC_LOONGARCH64_PREFIX is already set.")

        else:
            # now check for install dir.  If set then set the Prefix
            install_path = shell_environment.GetEnvironment(
            ).get_shell_var("GCC_LOONGARCH64_INSTALL")
            if install_path is None:
                return 0

            # make PREFIX to align with tools_def.txt
            prefix = os.path.join(install_path, "bin", "loongarch64-unknown-linux-gnu-")
            shell_environment.GetEnvironment().set_shell_var("GCC_LOONGARCH64_PREFIX", prefix)

        # now confirm it exists
        if not os.path.exists(shell_environment.GetEnvironment().get_shell_var("GCC_LOONGARCH64_PREFIX") + "gcc"):
            self.Logger.error(
                "Path for GCC_LOONGARCH64_PREFIX toolchain is invalid")
            return -2

        return 0
