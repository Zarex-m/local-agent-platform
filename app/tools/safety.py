import re


SHELL_RISK_RULES = [
    {
        "name": "recursive_force_delete",
        "pattern": r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)\b",
        "risk_level": "critical",
        "reason": "包含 rm -rf，可能递归强制删除文件，造成不可恢复的数据丢失",
    },
    {
        "name": "sudo",
        "pattern": r"\bsudo\b",
        "risk_level": "critical",
        "reason": "包含 sudo，会以管理员权限执行命令，影响范围可能超出当前项目",
    },
    {
        "name": "recursive_chmod",
        "pattern": r"\bchmod\s+-R\b",
        "risk_level": "high",
        "reason": "包含 chmod -R，会递归修改权限，可能破坏项目或系统文件权限",
    },
    {
        "name": "recursive_chown",
        "pattern": r"\bchown\s+-R\b",
        "risk_level": "high",
        "reason": "包含 chown -R，会递归修改文件归属，可能导致权限异常",
    },
    {
        "name": "curl_pipe_shell",
        "pattern": r"\b(curl|wget)\b.*\|\s*(sh|bash|zsh)\b",
        "risk_level": "critical",
        "reason": "包含 curl/wget 管道执行 shell，可能运行未经审计的远程脚本",
    },
    {
        "name": "disk_write",
        "pattern": r"\bdd\b.*\bof=",
        "risk_level": "critical",
        "reason": "包含 dd 写入目标设备或文件，可能覆盖磁盘或重要数据",
    },
    {
        "name": "format_disk",
        "pattern": r"\bmkfs(\.\w+)?\b",
        "risk_level": "critical",
        "reason": "包含 mkfs，可能格式化磁盘或分区",
    },
    {
        "name": "write_device",
        "pattern": r">\s*/dev/",
        "risk_level": "critical",
        "reason": "包含向 /dev 设备文件写入，可能影响系统设备或磁盘",
    },
]


RISK_ORDER = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}


def max_risk_level(levels: list[str], default: str = "low") -> str:
    if not levels:
        return default

    return max(levels, key=lambda level: RISK_ORDER.get(level, 0))


def analyze_shell_command(command: str | None) -> dict:
    if not command:
        return {
            "risk_level": "high",
            "requires_approval": True,
            "risk_reasons": ["run_shell 缺少 command 参数，但 shell 工具本身具有本地执行风险"],
            "matched_rules": [],
        }

    matched_rules = []
    risk_reasons = []
    risk_levels = []

    for rule in SHELL_RISK_RULES:
        if re.search(rule["pattern"], command, flags=re.IGNORECASE | re.DOTALL):
            matched_rules.append(rule["name"])
            risk_reasons.append(rule["reason"])
            risk_levels.append(rule["risk_level"])

    if matched_rules:
        return {
            "risk_level": max_risk_level(risk_levels, default="high"),
            "requires_approval": True,
            "risk_reasons": risk_reasons,
            "matched_rules": matched_rules,
        }

    return {
        "risk_level": "high",
        "requires_approval": True,
        "risk_reasons": ["run_shell 会在本机执行 shell 命令，可能读写文件、运行脚本或启动进程"],
        "matched_rules": [],
    }


def analyze_tool_risk(tool_name: str, tool_input: dict, default_risk_level: str = "low") -> dict:
    if tool_name == "run_shell":
        command = tool_input.get("command") if isinstance(tool_input, dict) else None
        return analyze_shell_command(command)

    requires_approval = default_risk_level in {"high", "critical"}

    return {
        "risk_level": default_risk_level,
        "requires_approval": requires_approval,
        "risk_reasons": [
            f"工具 {tool_name} 的默认风险等级为 {default_risk_level}"
        ] if requires_approval else [],
        "matched_rules": [],
    }


def format_risk_reason(tool_name: str, tool_input: dict, risk: dict) -> str:
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    reasons = risk.get("risk_reasons") or ["该操作需要用户审批"]

    lines = [
        f"工具 {tool_name} 需要审批",
        f"风险等级：{risk.get('risk_level', 'unknown')}",
        "风险原因：",
    ]

    for reason in reasons:
        lines.append(f"- {reason}")

    if command:
        lines.extend(
            [
                "命令：",
                command,
            ]
        )

    return "\n".join(lines)
