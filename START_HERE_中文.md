# Universal Day — 已整合的可运行项目

## 已串联的内容

- Member 1：`app.py`、`ui.py`、`static/index.html`、`static/app.js`、`static/styles.css` 及图片，保持原有网页形式。
- Member 2：`data/walking_time-matrix.csv`、`data/ride_durations.csv` 是此前提供的实际数据。
- Member 5：`data_adapter.py`、`route_optimizer.py`、`time_calculator.py`、`evaluate.py`、`integration.py`。
- 衔接层：**`my_optimizer.py`** 实现 Member 1 所需的 `get_attractions(current_location)`、`optimize(payload)`。
- Member 4：已附 `parkq_qaoa.py`；**必须另外从队友仓库复制 `parkq.py`、`attractions.csv`**，才能打开真实 QAOA 模式。没得到的文件不伪造。

## 在 PyCharm / macOS 立即运行：演示接通模式

1. 解压 ZIP，在 PyCharm 中将解压后的目录作为 Project 打开（注意不是旧项目中的单个 py 文件）。
2. 在 PyCharm Terminal 执行：

   ```bash
   export UNIVERSAL_OPTIMIZER_MODULE=my_optimizer
   export UNIVERSAL_SOLVER_MODE=demo
   python3 app.py
   ```

3. Chrome 打开 **http://127.0.0.1:8000** ，进入 Plan，选当前位置、喜好和时间，点击 Optimize。
4. 返回网页的是 **Member 5 的真实经典算法**，步行和游玩时长来自提供的 CSV；但 **候选组合不是 QAOA**。如果 `data/` 中没有真实 `line_up_*.csv`，排队为每个项目 15 分钟的明确模拟数据。网页会标注 **Demo route · Not QAOA**。
5. 在 Terminal 按 Control+C 停止服务器。

注意：如果 PyCharm 已经运行旧的 `app.py`，先停止旧服务，否则端口 8000 可能已被占用。

## 自动化测试

```bash
python3 -m unittest test_integration -v
```

## 切换真实 QAOA / 真实排队数据

1. 将 Member 2 的真正 `line_up_*.csv` 放到 `data/`（不是 `.webloc`），每个文件列名为 `id,time,wait`，时间为**北京当地日期和时间**。
2. 从团队仓库获取 `parkq.py`、`attractions.csv`，放在 `app.py` 同级。压缩包已包括 `parkq_qaoa.py`；如果队友更新过算法，用其最新版替换。
3. 在同一个 PyCharm Python Interpreter 安装依赖：

   ```bash
   python3 -m pip install 'qiskit>=2,<3' numpy scipy
   ```

4. 重新启动：

   ```bash
   export UNIVERSAL_OPTIMIZER_MODULE=my_optimizer
   export UNIVERSAL_SOLVER_MODE=qaoa
   export UNIVERSAL_START_TIME=09:00
   export UNIVERSAL_QAOA_MAXITER=40
   python3 app.py
   ```

真实模式不会自动回退到模拟队列或假 QAOA；若文件缺失会给出错误。`UNIVERSAL_START_TIME` 是历史排队记录日的北京当地时间，日期自动取**所有八个景点都有记录的最近一天**。这仍是历史排队估算，不是实时预测。

如果前端请求超过 120 秒，前端会提示超时。QAOA 真实运行速度需在你的本机验证；可以适当减少 `UNIVERSAL_QAOA_MAXITER` 或 `UNIVERSAL_QAOA_SHOTS`。

## 两个接口的具体处理

- `GET /api/attractions?current_location=R_1`：返回 `{'attractions': [...8个]}`；排队来自对应的真实或模拟记录；没有官方评分和步行米数，返回 `null`。
- `POST /api/optimize`：网页传 `{'current_location':'R_1','preferences':['magic'],'total_time_minutes':120}`；`my_optimizer.optimize` 将兴趣标签转换成 `R_1...R_8` 的数值喜好分，用 **相同评分** 传给 Member 4 和 5。
- 经典后处理负责候选组合去重、**考虑从当前位置到第一站的步行分钟数**、最短步行顺序、动态排队模拟、最多删 3 项、挑选最大喜好分可行方案。
- 返回 `{'steps': [...]}`，每站具有 `ride_id`、`walk_minutes`、`queue_minutes`、`ride_minutes`、`walk_distance_m:null`、`origin_distance_m:null`。`static/app.js` 已修改为允许缺少米数并显示 **Distance unavailable**。
- `steps=[]` 表示在约定规则下无可行方案（原始 `REOPTIMIZE` 信息仍在 `status/reason`）。当前**未自动反复运行 QAOA**。

## 本版的边界和约定

- 成功的本地测试仅验证了**演示模式**。真实 QAOA 依赖 Member 3 的 `parkq.py` 实际字段结构和真实 queue CSV，需要在完整团队代码下验证。
- 当前优化器枚举给定景点的**最短步行访问顺序**。如果动态排队时间随到达时间变化，它不保证全局最短**总游玩时间**。
- `UNIVERSAL_START_TIME` 默认 09:00；网页尚无选择具体日期时间的控件。
- 历史数据当天样本缺失、游玩到日期边界等情况可能导致错误；并没有真实实时预测服务。
- 前端项目名、照片和标签仍由 Member 1 的网页维护；偏好映射按对应的 `static/app.js` 标签匹配。
- 未实测米数时，**绝不把步行分钟数伪装成步行米数**。

## 如果你已经在 PyCharm 有自己的 QiskitHack 项目

可以在 PyCharm **另打开这个解压项目**，更容易检验 Member 1 网页是否能跑；整合通过后，再把 `my_optimizer.py`、修改过的 Member 5 文件和 `static/app.js` 合并到团队 GitHub 的功能分支。建议先检查差异，不要覆盖队友之后提交的更新。
