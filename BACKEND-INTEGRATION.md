# Universal Day 后端接入说明

## 先用示例跑通

解压源码包，在能看到 app.py 的目录打开 PowerShell，确认 python 命令可用，再运行：

```powershell
$env:UNIVERSAL_OPTIMIZER_MODULE = 'example_optimizer'
python app.py
```

在 Chrome 打开 http://127.0.0.1:8000 。进入 Plan，选择 Despicable Me Minion Mayhem（R_1），填 120 分钟，只勾选 Magic，再点 Optimize。预期返回 R_3。步行 7 分钟、排队 60 分钟、体验 15 分钟，合计 82 分钟，剩余 38 分钟。两种距离字段在首站均为 458 米，界面只显示距出发位置的距离。

example_optimizer.py 使用合成数据，最多返回一个可行景点。即使界面写着 Optimized itinerary，这一步也仅用于验证接口，没有运行 QAOA。

## 接入组员算法

在 app.py 同级创建 my_optimizer.py，实现两个函数。也可以从 example_optimizer.py 复制接口签名，并把示例数据与示例选点逻辑替换为组员的实现。

- get_attractions(current_location) 返回一个列表。每项包含 ride_id、wait_minutes、rating、origin_distance_m。app.py 将它包装为 {"attractions":[...]}，供 GET /api/attractions 使用。没有指标时可填 None，传到浏览器会变成 null。评分为 0–5，时间为分钟，距离为米。
- optimize(payload) 接收字典，通过 POST /api/optimize 调用。输入字段为 current_location、preferences、total_time_minutes。按最终游玩顺序返回 {"steps":[...]}。

输入示例：

```json
{"current_location":"R_1","preferences":["magic"],"total_time_minutes":120}
```

current_location 使用 R_1 到 R_8。preferences 可包含 thrill、magic、family、immersive。页面的游玩时间接受 30–720 的整数分钟，后端仍应独立校验输入。

示例输出：

```json
{"steps":[{"ride_id":"R_3","walk_minutes":7,"queue_minutes":60,"ride_minutes":15,"walk_distance_m":458,"origin_distance_m":458}]}
```

walk_minutes 和 walk_distance_m 表示从上一站到这一站的步行耗时和距离，第一站从用户选的出发景点计算。origin_distance_m 始终从用户选的出发景点计算。总耗时为每一站步行、排队和体验的合计。所有数值应是可序列化的非负有限数值，路线里不能有未知或重复的景点 ID。无可行路线返回 {"steps":[]}。

组员可以在 optimize 里用 QAOA 选项目，再用经典算法排序。排序后应重新计算各段步行时间，并检查最终路线没有超过时间限制。建议景点列表和算法共用排队、距离等数据。

接好后按 Ctrl+C 停止示例服务，在同一个 PowerShell 窗口运行：

```powershell
$env:UNIVERSAL_OPTIMIZER_MODULE = 'my_optimizer'
python app.py
```

环境变量填写模块名，不带 .py。保持接口格式一致即可沿用前端。app.py 只监听本机，上传 GitHub 只保存源码，不会启动 Python 服务。用 build_preview.py 生成的独立 HTML 走浏览器演示逻辑，接后端时请访问本地服务地址。
