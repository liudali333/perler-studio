# 拼豆图纸工坊（Perler Studio）

上传一张图片 → 一键变成可交互、可编辑、可导出的拼豆图纸页面。

复用「无畏契约拼豆专家」的确定性图纸管线（对齐搜索 + CIEDE2000 落色），
生成的图纸单文件自包含：25 套色板、色数档位、36–156 格、自定义尺寸、
逐格编辑、孤立像素清理、3D 成品预览、模拟烫豆、海报导出，双击就能打开。

## 启动

```bash
pip install -r requirements.txt
python setup_pipeline.py     # 从本机已装的「无畏契约拼豆专家」技能拷贝图纸算法到 pipeline/
python run.py                # 默认 http://127.0.0.1:8848
python run.py --port 9000    # 换端口
```

打开首页，拖一张图进去（PNG / JPG / WEBP / BMP / GIF，≤12MB），点「开始做图纸」，
大约 20 秒后新图纸页自动打开。左边「我的图纸」里留着所有做过的图，可随时再打开或下载。

## 出图设置

| 选项 | 说明 |
|---|---|
| 作品名 | 印在图纸标题与导出文件名上，不填用文件名 |
| 板子档位 | 36 / 52 / 78 / 104 / 156 格，任意勾选，至少一档 |
| 最多颜色数 | 8–40，默认 28；越少越好拼，越少越难认 |
| 去白边 | 去掉图片外圈的贴纸白边（默认开） |
| 合并相近颜色 | 画面出现花斑 / 交错色时打开 |

## 图纸页里的「换图重转」

图纸页面的「原图」页签底部有两个按钮：

- **裁切这一张**：拖框选主体，用裁出来的部分重做一版；
- **换一张图**：直接选新图重做。

新图纸在独立页面打开，当前图纸的编辑与拼豆进度不受影响。
本地 `file://` 直接双击打开图纸时这两个按钮自动隐藏（没有后台服务）。

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 上传页 |
| POST | `/api/convert` | 上传图转图纸（multipart：file / task / boards / default_size / max_colors / trim_border / merge_colors） |
| GET | `/api/jobs` | 全部图纸 |
| GET | `/api/jobs/{id}` | 单份状态 |
| GET | `/api/jobs/{id}/blueprint` | 图纸 HTML（内联打开） |
| GET | `/api/jobs/{id}/download` | 下载图纸 HTML |
| DELETE | `/api/jobs/{id}` | 删除 |

## 结构

```
perler-studio/
├── run.py              # 启动入口
├── perler/
│   ├── app.py          # FastAPI 服务
│   ├── converter.py    # 转换引擎（复用 pipeline）
│   └── jobs/           # 每份图纸一个目录（source.png + blueprint.html + meta.json）
├── pipeline/           # 拼豆图纸算法（不入库，python setup_pipeline.py 从拼豆专家技能拷贝）
├── templates/          # 图纸页面模板（含新增 js/remake.js、css/remake.css）
└── static/index.html   # 上传页
```

## 关于 pipeline/

图纸算法（对齐搜索、聚类落色、MARD 色板与图纸页面模板）来自 WorkBuddy
「无畏契约拼豆专家」技能包，本仓库不做二次分发，克隆后运行
`python setup_pipeline.py` 从本机已安装的技能里自动拷贝。

图片只在本机处理，`perler/jobs/` 里可随时手动备份或清理。

## 联系作者 & 赞赏支持

<table align="center">
  <tr>
    <td align="center">
      <b>联系作者</b><br><br>
      <img src="icons/wechat-qr.png" alt="微信联系方式" width="200"/><br>
      <small>扫码添加微信</small>
    </td>
    <td align="center">
      <b>赞赏支持</b><br><br>
      <img src="icons/zanshang.png" alt="赞赏码" width="200"/><br>
      <small>如果觉得有帮助，欢迎赞赏</small>
    </td>
  </tr>
</table>
