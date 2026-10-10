"""R26 橱柜净化除湿器功能可行性计算。

所有输入假设集中在本文件顶部；运行 `python3 r26_function_calc.py` 打印报告中用到的全部数字。
物性常数来源见报告"参考资料"一节。
"""
import math

# ---------- 物性常数 ----------
RV = 461.5          # 水蒸气气体常数 J/(kg·K)
MU_AIR = 1.84e-5    # 25 °C 空气动力黏度 Pa·s
RHO_AIR = 1.18      # 25 °C 空气密度 kg/m³
M_CAO, M_H2O, M_CAOH2 = 56.077, 18.015, 74.093   # g/mol
RHO_CAO, RHO_CAOH2 = 3.34, 2.21                  # g/cm³（固体密度）
DHF = {"CaO": -635.089, "CaOH2": -986.085, "H2O_l": -285.830, "H2O_g": -241.826}  # kJ/mol, NIST-JANAF 298.15 K

# ---------- 设计 / 场景假设 ----------
V_CAB = 0.65                    # 柜内容积 m³（0.60–0.70）
CAB_DIMS = (1.0, 0.55, 1.2)     # 示例柜体 m（宽、深、高），带 1 层隔板
T_C = 25.0
RH_OUT = (0.70, 0.80, 0.90)
RH_TARGET = 0.60
LEAK_ACH = (0.1, 0.3, 0.5, 1.0) # 关门渗漏换气 次/h
Q_FLOW = (1, 3, 5, 10)          # 实际穿过滤层的风量 m³/h
CAO_PRACTICAL = 0.28            # g 水 / g CaO（MFA CAMEO 表值）
CAO_MASS = (50, 100)            # g
D_DEVICE = 74.7e-3              # 整机外径 m
H_DEVICE = 155.0e-3
HOLE_AREA = 3485e-6             # 进风孔总面积 m²（1056 × Ø2.05 mm）
MNO2_D, MNO2_H = 50e-3, 15e-3   # 二氧化锰模块 m
LIT_TAU, LIT_ETA = 0.003, 0.40  # 文献：接触时间 0.003 s 时 HCHO 去除率 40%（K-birnessite）
BATTERY_WH = 3.6 * 3.0          # 18650 单节 3.0 Ah 估算
FAN_W = (0.22, 0.935)           # Noctua NF-A4x10 5V / NF-A6x25 5V 典型功率（参考）


def sat_vapor_pressure_pa(t_c):
    """Buck (1981) 饱和水汽压，水面。"""
    return 611.21 * math.exp((18.678 - t_c / 234.5) * (t_c / (257.14 + t_c)))


def vapor_density(t_c, rh):
    """g/m³"""
    return rh * sat_vapor_pressure_pa(t_c) / (RV * (t_c + 273.15)) * 1000


def ergun_dp(u, dp, eps, L):
    """Ergun 方程，床层压降 Pa。"""
    a = 150 * MU_AIR * (1 - eps) ** 2 * u / (eps ** 3 * dp ** 2)
    b = 1.75 * RHO_AIR * (1 - eps) * u ** 2 / (eps ** 3 * dp)
    return (a + b) * L


def section(title):
    print(f"\n=== {title} ===")


section("1. 柜内空气含水量（25 °C）")
es = sat_vapor_pressure_pa(T_C)
print(f"饱和水汽压 {es:.0f} Pa，饱和水汽密度 {vapor_density(T_C, 1.0):.2f} g/m³")
for rh in (0.9, 0.8, 0.7, 0.6, 0.5):
    print(f"RH {rh:.0%}: {vapor_density(T_C, rh):.2f} g/m³, 0.65 m³ 柜内 {vapor_density(T_C, rh) * V_CAB:.2f} g")
for rh in RH_OUT:
    d = (vapor_density(T_C, rh) - vapor_density(T_C, RH_TARGET)) * V_CAB
    print(f"一次性把空气从 {rh:.0%} 降到 60%: 需除去 {d:.2f} g 水（V=0.65）")

section("2. 柜体内表面与板材缓冲")
w, dpt, h = CAB_DIMS
area = 2 * (w * dpt + w * h + dpt * h) + 2 * w * dpt
print(f"示例柜体容积 {w * dpt * h:.3f} m³，内表面(含隔板两面) {area:.2f} m²，面积/容积 {area / (w * dpt * h):.1f} m²/m³")
for depth_mm in (0.5, 1.0):
    water = area * depth_mm / 1000 * 650 * (0.16 - 0.11) * 1000
    print(f"板材表层 {depth_mm} mm 平衡含水率 16%→11%（80%→60% RH）释放水量 ≈ {water:.0f} g（密度 650 kg/m³ 假设）")

section("3. 渗漏带入的持续湿负荷（目标 60% RH）")
loads = {}
for rh in RH_OUT:
    for lam in LEAK_ACH:
        g_day = lam * V_CAB * (vapor_density(T_C, rh) - vapor_density(T_C, RH_TARGET)) * 24
        loads[(rh, lam)] = g_day
        line = f"柜外 {rh:.0%}, λ={lam}/h: {g_day:6.1f} g/天, 需 CaO {g_day / CAO_PRACTICAL:6.1f} g/天"
        for m in CAO_MASS:
            line += f", {m} g CaO 可用 {m * CAO_PRACTICAL / g_day:5.1f} 天"
        print(line)

section("4. 氧化钙化学计量与热量")
cap_theory = M_H2O / M_CAO
v_cao, v_caoh2 = M_CAO / RHO_CAO, M_CAOH2 / RHO_CAOH2
dh_l = DHF["CaOH2"] - DHF["CaO"] - DHF["H2O_l"]
dh_g = DHF["CaOH2"] - DHF["CaO"] - DHF["H2O_g"]
print(f"理论吸水率 {cap_theory:.1%}（g 水/g CaO），文献实用值 {CAO_PRACTICAL:.0%}")
print(f"固体摩尔体积 CaO {v_cao:.1f} → Ca(OH)2 {v_caoh2:.1f} cm³/mol，体积比 {v_caoh2 / v_cao:.2f}")
print(f"反应热：液态水 {dh_l:.1f} kJ/mol，水蒸气 {dh_g:.1f} kJ/mol")
print(f"1 g CaO 完全消化放热 {-dh_g / M_CAO * 1000:.0f} J（吸水汽）")
for g_day in (5, 20, 40):
    print(f"吸湿 {g_day} g/天 → 平均放热 {g_day / M_H2O * -dh_g * 1000 / 86400:.2f} W")
mass_100_heat = 100 / M_CAO * -dh_l
print(f"100 g CaO 遇液态水完全反应放热 {mass_100_heat:.0f} kJ（≈ 把 {mass_100_heat * 1000 / (4.186 * 80):.0f} g 水从 20 °C 加热到 100 °C 的热量）")

section("5. 循环净化：衰减与稳态削减")
print("k = Q·η/V（次/h）；t90 = ln10/(k+λ)；稳态浓度比 = λ/(λ+k)")
for q in Q_FLOW:
    for eta in (0.5, 0.9):
        k = q * eta / V_CAB
        row = f"Q={q:>2} m³/h η={eta:.0%}: 等效换气 {k:5.2f} 次/h"
        for lam in (0.1, 0.3, 1.0):
            t90 = math.log(10) / (k + lam) * 60
            red = 1 - lam / (lam + k)
            row += f" | λ={lam}: t90 {t90:5.1f} min, 稳态削减 {red:.0%}"
        print(row)
print("\n衰减曲线（η=0.9, λ=0.3），相对浓度 %:")
for q in Q_FLOW:
    k = q * 0.9 / V_CAB + 0.3
    print(f"Q={q}: " + ", ".join(f"{t}min {100 * math.exp(-k * t / 60):.0f}" for t in (0, 15, 30, 45, 60, 90, 120)))

section("6. 进风孔与 MnO2 模块")
for q in Q_FLOW:
    qs = q / 3600
    v_hole = qs / HOLE_AREA
    a_m = math.pi * MNO2_D ** 2 / 4
    tau = a_m * MNO2_H / qs
    k_lit = -math.log(1 - LIT_ETA) / LIT_TAU
    eta_lit = 1 - math.exp(-k_lit * tau)
    eta_10 = 1 - math.exp(-k_lit / 10 * tau)
    print(f"Q={q:>2}: 孔口风速 {v_hole:.2f} m/s; MnO2 迎面风速 {qs / a_m:.2f} m/s, 空床接触时间 {tau * 1000:.1f} ms,"
          f" 按文献活性外推单程 HCHO {eta_lit:.0%}，活性只有 1/10 时 {eta_10:.0%}")

section("7. 颗粒床压降（Ergun, ε=0.40）与风扇静压")
d_bed = D_DEVICE - 2 * 2.5e-3 - 2 * 2e-3   # 扣壁厚与间隙，约 Ø65.7 mm
a_axial = math.pi * d_bed ** 2 / 4
print(f"轴向穿过 Ø{d_bed * 1000:.1f} mm 截面，面积 {a_axial * 1e4:.1f} cm²")
for q in Q_FLOW:
    u = q / 3600 / a_axial
    cells = []
    for dp_mm in (2, 3, 4):
        for L_mm in (10, 20):
            cells.append(f"d{dp_mm}/L{L_mm}: {ergun_dp(u, dp_mm / 1000, 0.40, L_mm / 1000):5.1f}")
    print(f"Q={q:>2} m³/h u={u:.2f} m/s | " + " | ".join(cells) + " Pa")
print("参考：Noctua NF-A4x10 5V 最大静压 1.78 mmH2O = 17.5 Pa；NF-A6x25 5V 2.18 mmH2O = 21.4 Pa（风量为 0 时）")

section("8. 活性炭床单程效率（外扩散控制，新鲜炭，Wakao-Funazkri）")
D_voc = 8.0e-6   # 典型 VOC 在空气中扩散系数 m²/s（甲苯约 8.5e-6）
for q in (3, 5):
    u = q / 3600 / a_axial
    for dp_mm, L_mm in ((3, 10), (3, 20)):
        dpm = dp_mm / 1000
        re = RHO_AIR * u * dpm / MU_AIR
        sc = MU_AIR / (RHO_AIR * D_voc)
        sh = 2 + 1.1 * sc ** (1 / 3) * re ** 0.6
        kc = sh * D_voc / dpm
        a_s = 6 * (1 - 0.4) / dpm
        ntu = kc * a_s * (L_mm / 1000) / u
        print(f"Q={q} d={dp_mm} mm L={L_mm} mm: Re={re:.0f}, Sh={sh:.1f}, NTU={ntu:.1f}, 单程上限 {1 - math.exp(-ntu):.1%}")

section("9. 续航（单节 18650，3.6 V × 3.0 Ah，转换效率 85%）")
for p in (0.3, 0.5, 1.0):
    hours = BATTERY_WH * 0.85 / p
    print(f"整机 {p} W: 连续 {hours:.0f} h；每小时运行 10 min 可用 {hours * 6 / 24:.1f} 天")

section("10. 整机可容纳 CaO 量级")
v_dev = math.pi * (D_DEVICE / 2) ** 2 * H_DEVICE * 1e6
print(f"整机外包络体积 {v_dev:.0f} cm³")
for frac in (0.2, 0.3):
    cav = v_dev * frac
    for fill in (0.5,):
        print(f"抽屉腔占 {frac:.0%} = {cav:.0f} cm³，按 50% 装填（给膨胀留空间）、堆积密度 0.9–1.0 g/cm³ → CaO {cav * fill * 0.9:.0f}–{cav * fill * 1.0:.0f} g")

# ---------- 硅胶替代方案 ----------
# 25 °C 吸附等温线数据点 (RH%, 吸附量 % 自重)，来源见报告"硅胶方案"一节
ISOTHERMS = {
    "Multicomp 非变色硅胶（典型值）": [(10, 6.5), (20, 12), (50, 27), (80, 36)],
    "双龙 A 型细孔（典型值）": [(50, 29.2), (90, 37.6)],
    "Multicomp 硅胶干燥剂（下限值）": [(20, 9.5), (50, 22), (90, 33)],
    "双龙 B 型粗孔（典型值）": [(20, 5.5), (50, 14.5), (90, 72)],
}
SILICA_BULK = (0.70, 0.77)      # g/cm³，Multicomp 数据表
SILICA_FILL = 0.95              # 硅胶不膨胀，可近乎装满
CAO_FILL, CAO_BULK = 0.50, (0.9, 1.0)
LATENT_25C = 2442               # J/g，25 °C 水的汽化潜热（吸附热不低于此值）


def interp(points, x):
    pts = sorted(points)
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        if x1 <= x <= x2:
            return y1 + (y2 - y1) * (x - x1) / (x2 - x1)
    return None


section("11. 硅胶：目标湿度下的有效吸水率")
for name, pts in ISOTHERMS.items():
    if "B 型" in name:   # B 型等温线呈 S 形，数据点之间不能线性插值
        print(f"{name}: 仅列数据点 " + ", ".join(f"{rh}% RH → {q}%" for rh, q in pts))
        continue
    vals = {rh: interp(pts, rh) for rh in (25, 50, 60)}
    print(f"{name}: " + ", ".join(f"{rh}% RH → {v:.1f}%" if v is not None else f"{rh}% RH → 无数据" for rh, v in vals.items()))

section("12. 整盒硅胶 vs 半盒氧化钙（抽屉腔 136–204 cm³）")
for cav in (136, 170, 204):
    cao_m = [cav * CAO_FILL * d for d in CAO_BULK]
    si_m = [cav * SILICA_FILL * d for d in SILICA_BULK]
    cao_w = [m * CAO_PRACTICAL for m in cao_m]
    si_w_lo = si_m[0] * 0.2475    # 下限值曲线在 60% RH
    si_w_hi = si_m[1] * 0.3125    # 双龙 A 型典型值在 60% RH
    print(f"腔体 {cav} cm³: CaO {cao_m[0]:.0f}–{cao_m[1]:.0f} g → 吸水 {cao_w[0]:.0f}–{cao_w[1]:.0f} g；"
          f"硅胶 {si_m[0]:.0f}–{si_m[1]:.0f} g → 60% RH 前吸水 {si_w_lo:.0f}–{si_w_hi:.0f} g")

section("13. 中间值对比的可用天数（腔体 170 cm³，目标 60% RH）")
cao_mid = 170 * CAO_FILL * 0.95 * CAO_PRACTICAL
si_mid = 170 * SILICA_FILL * 0.735 * 0.28
print(f"CaO 中间值 {cao_mid:.1f} g 水；硅胶中间值 {si_mid:.1f} g 水（吸水率取 28%），倍数 {si_mid / cao_mid:.2f}")
for rh in RH_OUT:
    print(f"柜外 {rh:.0%}: " + " | ".join(
        f"λ={lam}: CaO {cao_mid / loads[(rh, lam)]:.1f} 天 / 硅胶 {si_mid / loads[(rh, lam)]:.1f} 天" for lam in LEAK_ACH))

section("14. 硅胶再生能耗下限与变色指示时机")
for w in (23, 33, 46):
    e_wh = w * LATENT_25C / 3600
    print(f"脱附 {w} g 水至少需 {e_wh:.1f} Wh（仅汽化潜热），单节 18650 约 {BATTERY_WH:.1f} Wh")
q25 = interp(ISOTHERMS["Multicomp 非变色硅胶（典型值）"], 25)
q60 = interp(ISOTHERMS["Multicomp 非变色硅胶（典型值）"], 60)
print(f"橙/绿变色约在 20–35% RH 变色：25% RH 时吸附量约 {q25:.1f}%，仅为 60% RH 容量 {q60:.1f}% 的 {q25 / q60:.0%}")
