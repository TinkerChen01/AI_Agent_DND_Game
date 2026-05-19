# 定时提醒机制 — cron job 配置

> 对应 dnd-dm §4.5 定时提醒机制。纯提醒，不做任何文件读写或状态检测。

---

## 配置

**名称：** `dnd-reminder-cron`
**调度：** `*/20 * * * *`（每 20 分钟）
**工具集：** 无需特殊工具（纯发送消息）
**交付：** `origin`（发回当前对话）

### Prompt

```
D&D 游戏进行中，20分钟定时提醒。

请向当前对话发送以下消息（原文，不要修改）：
"陈总，20分钟到了，请提醒我检查状态更新或进行存档哦～"

发送后任务即完成，不要做其他任何事情。
```

---

## 游戏启动时创建

游戏会话开始时，DM 执行：

```
cronjob action='create' \\
  name='dnd-reminder-cron' \\
  schedule='*/20 * * * *' \\
  prompt='D&D 游戏进行中，20分钟定时提醒。\n\n请向当前对话发送以下消息（原文，不要修改）：\n"陈总，20分钟到了，请提醒我检查状态更新或进行存档哦～"\n\n发送后任务即完成，不要做其他任何事情。' \\
  deliver='origin'
```

## 游戏退出时清理

```
cronjob action='list'    # 查看 job_id
cronjob action='remove' job_id='dnd-reminder-cron'
```
