# Huawei Ranking Tracker

这个仓库会定时抓取华为云开发者大赛指定队伍的排名，并用 GitHub Pages 展示当前排名、分数、Top 20 和历史曲线。

默认目标已经配置为：

- 比赛页面：<https://developer.huaweicloud.cn/competition/information/1300000256/ranking>
- 队伍：`hid_rl3ei4awlp8cx6k`

## 本地更新

```bash
python scripts/update_rankings.py
```

生成的数据在：

- `site/data/rankings.json`
- `site/data/history.json`
- `site/data/cann_tasks.json`

本地预览：

```bash
python -m http.server 8000 -d site
```

然后打开 <http://localhost:8000>。

## GitHub 使用

1. 新建一个 GitHub 仓库。
2. 把本目录推送到该仓库。
3. 在仓库 `Settings -> Pages -> Build and deployment` 中选择 `GitHub Actions`。
4. 到 `Actions` 页面手动运行一次 `Update ranking and deploy Pages`。

之后 GitHub Actions 会每小时自动更新一次排名数据和 CANN 社区任务报名统计，并重新部署页面。

## CANN 社区任务统计

```bash
python scripts/update_cann_tasks.py
```

脚本会自动抓取 <https://gitcode.com/org/cann/discussions/22> 中 2026-05-29 以后 20 个 `20260529-*` 开发任务的报名评论，生成 `site/data/cann_tasks.json`。页面入口是 `site/cann-tasks.html`，也可以从首页右上角 `CANN Tasks` 进入。

## 修改监控目标

编辑 `config.json`：

```json
{
  "targets": [
    {
      "name": "Huawei Algorithm Challenge 37",
      "competition_url": "https://developer.huaweicloud.cn/competition/information/1300000256/ranking",
      "competition_url_id": "1300000256",
      "team": "hid_rl3ei4awlp8cx6k"
    }
  ],
  "page_size": 100,
  "history_limit": 300
}
```

`team` 可以填写队伍名或接口里的 `team_id`。如果要固定某个赛段，也可以在目标里补充 `stage_id`。
