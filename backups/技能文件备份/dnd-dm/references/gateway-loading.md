# 网关平台加载说明

## 微信（WeChat）/ Telegram

正确的加载方式是直接发送 **`/dnd-dm`**。

每个 Skill 自动注册为独立的斜杠命令，Skill 的名称就是命令本身。不是 `/skill + 名称` 的形式。

### 已知陷阱：网关缓存

**Skill 文件创建/修改后，网关需要重启才能识别新命令。**

因为 `scan_skill_commands()` 缓存在内存中，仅在启动时或平台切换时刷新。如果在网关运行期间新增了 Skill 文件，直接发 `/dnd-dm` 会得到 "Unknown command"。

```bash
# 在 CLI 终端中执行：
hermes gateway restart
```

重启后网关会重新扫描 `~/.hermes/skills/`，新 Skill 的斜杠命令即可使用。

### 如何确认是否生效

检查网关日志中的 `/dnd-dm` 记录：
```bash
grep "dnd-dm\|Unrecognized.*dnd-dm" ~/.hermes/logs/gateway.log | tail -5
```

如果看到 "Unrecognized slash command /dnd-dm" → 网关未重启，Skill 未被识别。
如果没有任何 /dnd-dm 日志记录 → 命令已被正确处理。

### 常见错误

| ❌ 错误的 | ✅ 正确的 |
|-----------|----------|
| `/skill dnd-dm` | `/dnd-dm` |
| `/skill dnd-存档` | `/dnd-存档` |

### 回退方案

如果 `/dnd-dm` 不可用（例如"Unknown command"），代理可以通过 `skill_view(name='dnd-dm')` 手动读取 Skill 内容。此时规则在会话上下文中生效，而非 system prompt。

启动协议（§3.1 读取顺序 + §3.4 陷阱警示）在 `skill_view()` 模式下同样适用——必须先读 L2 再叙事。
