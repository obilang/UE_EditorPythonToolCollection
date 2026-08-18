import os
import sys
import csv
import statistics
from typing import List, Optional, Dict, Tuple
import math

# Try to make sure bundled Libs (e.g. PIL) are importable when run from UE or VS Code
def _ensure_libs_on_path():
	here = os.path.dirname(os.path.abspath(__file__))
	libs = os.path.normpath(os.path.join(here, "..", "..", "Libs"))
	if os.path.isdir(libs) and libs not in sys.path:
		sys.path.append(libs)


_ensure_libs_on_path()

try:
	from PIL import Image, ImageDraw, ImageFont
except Exception:  # pragma: no cover - fallback if PIL isn't available
	Image = ImageDraw = ImageFont = None


def _is_float(s: str) -> bool:
	try:
		float(s)
		return True
	except Exception:
		return False


def _read_csv_header_and_rows(csv_path: str) -> Tuple[List[str], List[List[str]]]:
	with open(csv_path, newline="", encoding="utf-8") as f:
		reader = csv.reader(f)
		rows = list(reader)
	if not rows:
		raise ValueError("CSV is empty")

	header = rows[0]
	data_rows = []
	# Filter out metadata or malformed rows (e.g., trailing UE metadata starting with [HasHeaderRowAtEnd])
	for r in rows[1:]:
		if not r:
			continue
		# Some profilers append a single long key-value line at the end beginning with [
		first_cell = r[0] if len(r) > 0 else ""
		if isinstance(first_cell, str) and first_cell.startswith("["):  # metadata tail
			break
		# Keep rows that have at least as many columns as header (UE CSV usually matches or exceeds)
		if len(r) >= len(header):
			data_rows.append(r[: len(header)])
	return header, data_rows


def _extract_series(header: List[str], rows: List[List[str]], column_name: str) -> List[Optional[float]]:
	series: List[Optional[float]] = []
	try:
		idx = header.index(column_name)
	except ValueError:
		return [None] * len(rows)

	for r in rows:
		v = r[idx].strip() if idx < len(r) else ""
		if v == "" or v.lower() == "nan" or v.lower() == "inf" or v.lower() == "-inf":
			series.append(None)
		else:
			try:
				series.append(float(v))
			except Exception:
				series.append(None)
	return series


def _normalize_to_ms(values: List[Optional[float]]) -> List[Optional[float]]:
	# Heuristic: if median of present values < 0.5, likely seconds; convert to ms.
	present = [v for v in values if v is not None]
	if not present:
		return values
	med = statistics.median(present)
	if med < 0.5:  # seconds -> ms
		return [None if v is None else v * 1000.0 for v in values]
	return values  # already ms


def _moving_average(seq: List[Optional[float]], window: int) -> List[Optional[float]]:
	if window <= 1:
		return seq[:]
	out: List[Optional[float]] = [None] * len(seq)
	buf: List[float] = []
	sum_val = 0.0
	for i, v in enumerate(seq):
		if v is not None:
			buf.append(v)
			sum_val += v
		else:
			buf.append(float("nan"))
		if len(buf) > window:
			old = buf.pop(0)
			if not (old != old):  # not NaN
				sum_val -= old
		# compute average ignoring NaNs
		valid = [x for x in buf if not (x != x)]
		out[i] = (sum(valid) / len(valid)) if valid else None
	return out


def _stats(values_ms: List[Optional[float]]) -> Dict[str, float]:
	v = [x for x in values_ms if isinstance(x, (float, int))]
	if not v:
		return {"count": 0, "avg": float("nan"), "min": float("nan"), "max": float("nan"), "p99": float("nan")}
	v_sorted = sorted(v)
	n = len(v)
	p99 = v_sorted[min(n - 1, max(0, int(round(n * 0.99)) - 1))]
	return {
		"count": n,
		"avg": sum(v) / n,
		"min": v_sorted[0],
		"max": v_sorted[-1],
		"p99": p99,
	}


def _draw_axes(draw, x0: int, y0: int, x1: int, y1: int, color=(220, 220, 220)):
	# border rectangle
	draw.rectangle([x0, y0, x1, y1], outline=color, width=1)


def _draw_ticks(
	draw,
	font: Optional[object],
	x0: int,
	y0: int,
	x1: int,
	y1: int,
	y_max: float,
	n_y_ticks: int = 6,
	x_tick_step: Optional[int] = None,
	y_ticks: Optional[List[float]] = None,
):
	# # Y ticks (ms)
	# for i in range(n_y_ticks + 1):
	# 	t = i / n_y_ticks
	# 	y = int(y1 - t * (y1 - y0))
	# 	draw.line([x0, y, x1, y], fill=(240, 240, 240))
	# 	label = f"{t * y_max:.0f} ms"
	# 	if font:
	# 		draw.text((x0 - 55, y - 7), label, fill=(120, 120, 120), font=font)
	# Y ticks (ms)
	def _fmt_ms(v: float) -> str:
		# Use sensible decimals and drop trailing zeros
		if abs(v - round(v)) < 1e-6 or v >= 10:
			s = f"{v:.0f}"
		elif v >= 1:
			s = f"{v:.1f}"
		else:
			s = f"{v:.2f}"
		return f"{s} ms"

	if y_ticks is None:
		# fallback: linear spacing
		y_ticks = [i * (y_max / n_y_ticks) for i in range(n_y_ticks + 1)]

	for val in y_ticks:
		# clamp just in case
		val = max(0.0, min(y_max, val))
		t = 0 if y_max <= 0 else val / y_max
		y = int(y1 - t * (y1 - y0))
		draw.line([x0, y, x1, y], fill=(240, 240, 240))
		if font:
			draw.text((x0 - 55, y - 7), _fmt_ms(val), fill=(120, 120, 120), font=font)
   
	# X ticks by frame index if provided
	if x_tick_step is not None and x_tick_step > 0:
		for x in range(x0, x1 + 1, x_tick_step):
			draw.line([x, y1, x, y1 + 4], fill=(200, 200, 200))
   
   


def _plot_polyline(
	draw,
	points: List[Tuple[int, int]],
	color=(52, 152, 219),
	width=2,
):
	if len(points) < 2:
		return
	# Draw small segments to approximate a polyline
	for i in range(1, len(points)):
		draw.line([points[i - 1], points[i]], fill=color, width=width)


def _build_points(values_ms: List[Optional[float]], x0: int, y0: int, x1: int, y1: int, y_max: float) -> List[Tuple[int, int]]:
	n = len(values_ms)
	w = max(1, x1 - x0)
	points: List[Tuple[int, int]] = []
	for i, v in enumerate(values_ms):
		if v is None:
			continue
		t = i / max(1, n - 1)
		x = x0 + int(t * w)
		yy = y1 - int(min(1.0, max(0.0, v / y_max)) * (y1 - y0))
		points.append((x, yy))
	return points


def _pick_y_max(series_ms: List[List[Optional[float]]]) -> float:
	vals: List[float] = []
	for s in series_ms:
		vals.extend([v for v in s if v is not None])
	if not vals:
		return 5.0
	m = max(vals)
	# Round up to a nice number (nearest 5ms step)
	step = 5.0
	return max(5.0, (int(m / step) + 1) * step)


def _nice_y_scale(y_max: float, target_ticks: int = 6) -> Tuple[float, List[float]]:
	"""
	Returns (nice_y_max, tick_values). Chooses a pleasant tick step from [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50].
	"""
	nice_steps = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100]
	step = nice_steps[-1]
	for s in nice_steps:
		if y_max / s <= target_ticks:
			step = s
			break
	nice_max = max(step, math.ceil(y_max / step) * step)
	ticks = [i * step for i in range(int(round(nice_max / step)) + 1)]
	return nice_max, ticks


def generate_volumetric_cloud_plot(
	csv_path: str,
	out_path: Optional[str] = None,
	width: int = 1600,
	height: int = 600,
	smooth_window: int = 1,
	assume_seconds: bool = False,
) -> str:
	if Image is None:
		raise RuntimeError("PIL is not available. Please ensure Libs/PIL is present or install Pillow.")

	header, rows = _read_csv_header_and_rows(csv_path)

	# Extract the single series needed
	gpu = _extract_series(header, rows, "GPU/ShadowDepths")
	if all(v is None for v in gpu):
		raise ValueError("Column 'GPU/ShadowDepths' not found or has no numeric data in the CSV.")

	# Units: for GPU/* series, values are typically already in milliseconds.
	# Allow an override to interpret as seconds and convert to ms when requested.
	if assume_seconds:
		gpu = [None if v is None else v * 1000.0 for v in gpu]

	# Optional smoothing
	gpu_s = _moving_average(gpu, smooth_window)

	# Compute stats
	gpu_stats = _stats(gpu_s)

	# Canvas and plot area
	margin_left = 80
	margin_right = 20
	margin_top = 30
	margin_bottom = 60
	img = Image.new("RGB", (width, height), (255, 255, 255))
	draw = ImageDraw.Draw(img)
	try:
		font = ImageFont.truetype("arial.ttf", 14)
		font_small = ImageFont.truetype("arial.ttf", 12)
	except Exception:
		font = ImageFont.load_default()
		font_small = ImageFont.load_default()

	x0 = margin_left
	y0 = margin_top
	x1 = width - margin_right
	y1 = height - margin_bottom

    # Axes and grid
    # y_max = _pick_y_max([gpu_s])
	y_max_raw = _pick_y_max([gpu_s])
	y_max, y_ticks = _nice_y_scale(y_max_raw, target_ticks=6)
	_draw_axes(draw, x0, y0, x1, y1)
    # X tick step roughly every ~100px
	x_tick_step = max(100, int((x1 - x0) / 12))
    # _draw_ticks(draw, font_small, x0, y0, x1, y1, y_max, n_y_ticks=6, x_tick_step=x_tick_step)
	_draw_ticks(draw, font_small, x0, y0, x1, y1, y_max, n_y_ticks=6, x_tick_step=x_tick_step, y_ticks=y_ticks)

    # Curves
	color = (142, 68, 173)  # purple
	gpu_points = _build_points(gpu_s, x0, y0, x1, y1, y_max)
	_plot_polyline(draw, gpu_points, color, width=2)

	legend_items = [("GPU/ShadowDepths", gpu_stats)]

	# Title
	title = f"GPU/ShadowDepths (ms) — {os.path.basename(csv_path)}"
	draw.text((x0, 8), title, fill=(20, 20, 20), font=font)

	# Legend with stats
	legend_x = x0
	legend_y = y1 + 8
	series_color = color  # single series color
	for name, stats in legend_items:
		# line sample
		draw.line([legend_x, legend_y + 10, legend_x + 25, legend_y + 10], fill=series_color, width=4)
		legend_x += 32
		text = (
			f"{name}: avg {stats['avg']:.2f} ms | p99 {stats['p99']:.2f} | min {stats['min']:.2f} | max {stats['max']:.2f}"
		)
		draw.text((legend_x, legend_y), text, fill=(40, 40, 40), font=font_small)
		legend_y += 18
		legend_x = x0

	# Output path
	if out_path is None:
		base, _ = os.path.splitext(csv_path)
		out_path = base + "_ShadowDepths.png"
	os.makedirs(os.path.dirname(out_path), exist_ok=True)
	img.save(out_path)
	return out_path


def _find_latest_profile_csv(search_dir: str) -> Optional[str]:
	if not os.path.isdir(search_dir):
		return None
	candidates = [
		os.path.join(search_dir, f)
		for f in os.listdir(search_dir)
		if f.lower().endswith(".csv") and f.lower().startswith("profile")
	]
	if not candidates:
		return None
	candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
	return candidates[0]


def main(argv: List[str]) -> int:
	import argparse

	parser = argparse.ArgumentParser(description="Plot the 'GPU/ShadowDepths' column from Unreal CSV to a PNG curve chart.")
	parser.add_argument(
		"-i", "--input", dest="csv_path", default=None, help="Path to CSV file. Defaults to latest profile*.csv in current folder."
	)
	parser.add_argument("-o", "--output", dest="out_path", default=None, help="Path to output PNG.")
	parser.add_argument("--width", type=int, default=1600, help="Image width in pixels (default 1600)")
	parser.add_argument("--height", type=int, default=600, help="Image height in pixels (default 600)")
	parser.add_argument(
		"--smooth", type=int, default=1, help="Moving average window in frames (default 1 = no smoothing)"
	)
	parser.add_argument("--assume-seconds", action="store_true", help="Treat CSV values as seconds and convert to ms")

	args = parser.parse_args(argv)

	csv_path = args.csv_path
	if csv_path is None:
		csv_path = _find_latest_profile_csv(os.path.dirname(os.path.abspath(__file__)))
		if csv_path is None:
			print("No input CSV provided and no profile*.csv found in this folder.")
			return 2
		print(f"Using latest CSV: {csv_path}")

	if not os.path.isfile(csv_path):
		print(f"CSV not found: {csv_path}")
		return 2

	try:
		out = generate_volumetric_cloud_plot(
			csv_path=csv_path,
			out_path=args.out_path,
			width=args.width,
			height=args.height,
			smooth_window=max(1, args.smooth),
			assume_seconds=args.assume_seconds,
		)
		print(f"Wrote: {out}")
		return 0
	except Exception as e:
		print(f"Error: {e}")
		return 1


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))

