# Universal Day — 英文路线规划前端

无后端展示：先运行 python build_preview.py 生成 Universal-Day-English.html，再用浏览器打开生成的文件。生成与预览均可离线完成。

源码运行：Python 3.10+，在本目录运行 python app.py，再打开 http://127.0.0.1:8000 。无第三方依赖。

## 功能与数据

预算、费用、单项排队上限已移除。按用户偏好和总时间生成演示路线，总时间包含步行、排队和游玩，不含休息、餐饮或返程。评分不参与演示优化。

卡片显示排队时间和距用户当前位置的距离，切换位置立即更新，支持 Nearest to you 排序。结果分别显示上一站到该项目的步行距离、每个项目距用户出发位置的距离、总步行距离、耗时和剩余时间，支持 JSON 导出。

评分、评价数量、排队、体验时长和坐标全部为样本。距离使用虚构坐标，每格 150 米，加 150 米区域偏移（同区亦为估算），步行速度按 70 米/分钟。不能用于真实导航。演示算法为基于偏好匹配和耗时的简单贪心规则，不保证最优，未调用 QAOA。

## 代码结构

- app.py：本地页面服务，以及 GET /api/attractions 和 POST /api/optimize 接口。
- example_optimizer.py：使用合成数据验证两个接口的示例模块。
- ui.py：页面渲染入口。
- static/index.html：英文表单与结果容器。
- static/styles.css：响应式样式。
- static/app.js：数据、距离、交互、结果校验与导出。
- Universal-Day-English.html：可直接双击打开或转发的单文件演示。
- build_preview.py：修改源码后，运行 python build_preview.py 重新生成单文件演示。

修改页面时以 static/ 中的三个文件为准，不要同时修改单文件演示。无后端展示先生成再双击 Universal-Day-English.html；需要开发或对接算法时运行 python app.py。

## 算法对接

新建 my_optimizer.py，提供 optimize(payload: dict) -> dict。由组员实现 QAOA 选项目、经典算法排序。PowerShell 设置后启动：

```powershell
$env:UNIVERSAL_OPTIMIZER_MODULE = 'my_optimizer'
python app.py
```

设置 UNIVERSAL_OPTIMIZER_MODULE 后，由 app.py 自动启用后端模式，无需修改前端。独立 HTML 保持离线演示。

请求：

```json
{"current_location":"R_1","preferences":["thrill","magic"],"total_time_minutes":300}
```

位置枚举：R_1 到 R_8，分别对应当前位置下拉框中的八个景点。出发景点与目标景点相同时，演示距离为 0 米。
偏好枚举：thrill, magic, family, immersive。

返回（steps 按最终游玩顺序排列）：

```json
{"steps":[{"ride_id":"R_3","walk_minutes":15,"queue_minutes":45,"ride_minutes":15,"walk_distance_m":900,"origin_distance_m":900}]}
```

walk_distance_m：从上一站到此项目的步行距离；首站从用户当前位置出发。
origin_distance_m：始终从用户提交的出发位置到此项目的距离。
时间单位为分钟，距离单位为米。全部为非负有限数字。无解返回 {"steps":[]}。

前端拒绝缺失距离、无效数值、未知或重复 ID、超出总时间的结果。后端模式不使用虚构坐标补齐距离字段。正式服务须独立校验输入，为卡片列表另接评分、实时排队与实际距离接口；未配置后端模块时，卡片使用标明为 demo 的样本数据。

本地服务只监听本机，适用于课程原型。

调查面板仅包含当前位置、预计总游玩时间和喜好三个输入。服务根据后端模块配置选择数据模式。时间轴显示从游玩开始算起的相对时间，无需输入开始时刻。

## 景点数据接口

服务调用同一个后端模块的 get_attractions(current_location: str) -> list[dict]。
前端请求 GET /api/attractions?current_location=R_1，切换出发位置时重新加载。
接口响应由 app.py 包装为：

```json
{"attractions":[{"ride_id":"R_3","wait_minutes":45,"rating":4.7,"origin_distance_m":900}]}
```

ID 沿用 R_1 到 R_8。三个指标都需要提供，缺失数据时填 null。评分为 0–5，排队单位为分钟，距离单位为米。可以省略暂无数据的景点，卡片会显示指标不可用。后端请求出错时，界面会显示错误，不会把演示数据当成真实数据。项目名称、照片和类别由前端维护。

建议 get_attractions 和 optimize 读取同一份园区数据。POST /api/optimize 的请求和返回格式见上文。

## 运行示例后端

在解压后的 universal-planner 文件夹打开 PowerShell，运行：

```powershell
$env:UNIVERSAL_OPTIMIZER_MODULE = 'example_optimizer'
python app.py
```

在 Chrome 打开 http://127.0.0.1:8000 。选择 R_1 作为当前位置，填写 120 分钟，喜好只勾选 Magic，再点 Optimize。示例应返回 R_3，步行 7 分钟、排队 60 分钟、体验 15 分钟，合计 82 分钟。

example_optimizer.py 使用合成数据，最多返回一个可行景点，仅用于演示接口。组员可复制它为 my_optimizer.py，用实际数据实现 get_attractions，用选点及排序算法实现 optimize，再把环境变量改成 my_optimizer 并重启。多站路线中，每一站的 walk_distance_m 从上一站计算，origin_distance_m 始终从出发点计算。

