# Huawei Ranking Tracker

这个项目通过 GitHub Actions 自动抓取数据，并通过 GitHub Pages 发布静态看板。

## GitHub Pages

- 首页：<https://yunhanbb.github.io/huawei-ranking-tracker/>
- CANN 社区任务统计：<https://yunhanbb.github.io/huawei-ranking-tracker/cann-tasks.html>

## 页面内容

首页展示华为云开发者大赛指定队伍的公开榜单信息：

- 当前排名、分数、参赛阶段和榜单刷新时间
- Top 20 排名分数柱状图
- 提交历史中的最佳成绩、最近提交和成功评分比例

当前默认监控目标：

- 比赛页面：<https://developer.huaweicloud.cn/competition/information/1300000256/ranking>
- 队伍：`hid_rl3ei4awlp8cx6k`

CANN 社区任务统计页展示 GitCode CANN 讨论页中的报名情况：

- 来源讨论：<https://gitcode.com/org/cann/discussions/22>
- 统计范围：2026-05-29 以后发布的报名评论
- 任务范围：20 个 `20260529-*` 开发任务
- 展示内容：每个任务的报名申请数量、任务状态、承接队伍、奖金和最近申请记录

## 自动更新

`.github/workflows/update-and-deploy.yml` 会每小时运行一次，也可以在 GitHub Actions 页面手动触发。

每次运行会：

1. 抓取华为云比赛排名数据，更新 `site/data/rankings.json` 和 `site/data/history.json`。
2. 抓取 CANN 社区任务讨论数据，更新 `site/data/cann_tasks.json`。
3. 将更新后的数据提交回仓库。
4. 使用 GitHub Pages 部署 `site/` 目录。

## 修改监控目标

监控的比赛和队伍配置在 `config.json`：

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

`team` 可以填写队伍名或接口里的 `team_id`。如果要固定某个赛段，可以在目标里补充 `stage_id`。
