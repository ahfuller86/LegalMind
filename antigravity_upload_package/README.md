# LegalMind Agent for Antigravity

This package contains the LegalMind agent definition and tools for the Antigravity Agent Manager.

## Contents
- `openclaw-agent/`: The agent definition (AGENTS.md, SKILL.md files, etc.).
- `legalmind-tools.js`: The compiled plugin script that defines the tools (including the new file upload capability).

## Installation

1.  Upload the `openclaw-agent` folder to your Antigravity workspace or agent configuration.
2.  Register the `legalmind-tools.js` plugin in your agent environment. This plugin provides the `legalmind.*` tools, including `legalmind.evidence.upload`.

## New Features
- **File/Folder Upload**: Use the `legalmind.evidence.upload` tool to upload local files or folders to the LegalMind Engine. Folders are automatically zipped.
