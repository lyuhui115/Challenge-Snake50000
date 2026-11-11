extends Node
## FlagManager —— 到达 500 分时用 KEY 现场"铸"出 flag；校验不通过则返回诱饵。
##
## 二进制中从头到尾不存在 flag 字符串（连密文都没有）：
##   KEY(分片存储) --FNV-1a--> 32bit 种子 --xorshift32--> 字符流 --字母表--> flag
## 玩家反编译后拿到 KEY 和算法，需要离线复现整个流程才能算出 flag。
##
## 反作弊逻辑（防直接改内存分数）:
##   1. 每次真实吃食物都会记录时间戳 (register_food)
##   2. reveal() 校验: 分数 == 吃食物次数 * 单次分值
##   3. 校验: 最初与最后一次吃食物的时间跨度 >= 次数 * 最小间隔
## 任一不满足 => 返回 DECOY（假 flag，交给平台会判错）

const POINTS_PER_FOOD := 10

# 两次吃食物允许的最小物理间隔(毫秒)。
# 必须小于 main.gd 的 MIN_STEP(0.040s=40ms)，否则极限速通玩家可能被误伤。
const MIN_FOOD_GAP_MS := 30

# 诱饵：字符串搜 flag{ 或直接改内存分的人会拿到它
const DECOY := "flag{Y0u_W1sh_It_W4s_Th1s_E4sy}"

const ALPHABET := "5n4k3G0dTc7f9"
const FLAG_LEN := 24

var _food_times: Array[int] = []


# KEY 分片存储，strings 直接搜不到完整串（改 KEY 后记得用 tools/compute_flag.py 算出新 flag）
func _key() -> String:
	return "G0d0t" + "-5n4k3" + "-c7f2025" + "-x7k9m2"


func reset() -> void:
	_food_times.clear()


func register_food() -> void:
	_food_times.append(Time.get_ticks_msec())


func reveal(score: int) -> String:
	if not _check(score):
		push_warning("integrity check failed")
		return DECOY
	return _mint()


func _check(score: int) -> bool:
	if _food_times.is_empty():
		return false
	# 分数必须与真实吃食物次数一致（防只改分数）
	if score != _food_times.size() * POINTS_PER_FOOD:
		return false
	# 吃食物节奏必须物理可达（防一帧内批量刷分）
	if _food_times.size() >= 2:
		var span: int = _food_times[_food_times.size() - 1] - _food_times[0]
		var min_span: int = (_food_times.size() - 1) * MIN_FOOD_GAP_MS
		if span < min_span:
			return false
	return true


func _mint() -> String:
	var s := _fnv1a(_key())
	var out := ""
	for _i in FLAG_LEN:
		s = _xs(s)
		out += ALPHABET[s % ALPHABET.length()]
	return "flag{" + out + "}"


func _fnv1a(text: String) -> int:
	var h := 2166136261
	for b in text.to_utf8_buffer():
		h = ((h ^ b) * 16777619) & 0xFFFFFFFF
	return h


func _xs(s: int) -> int:
	s = (s ^ ((s << 13) & 0xFFFFFFFF)) & 0xFFFFFFFF
	s = s ^ (s >> 17)
	s = (s ^ ((s << 5) & 0xFFFFFFFF)) & 0xFFFFFFFF
	return s
