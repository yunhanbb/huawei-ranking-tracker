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

之后 GitHub Actions 会每 10 分钟自动更新一次排名数据并重新部署页面。

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
