# Draft upstream report: GDScript skips an `if` body after `await` when lambdas capture locals (Godot 4.7.2)

Status: DRAFT for the human to file at https://github.com/godotengine/godot/issues (agents do not post upstream).
Found in run 1, task T032 (docs/qa/reports/M1-2026-10-28.md, finding N1); reproduced independently by the reviewer.

**Godot version:** 4.7.2.stable (ed1daf0bf), Linux x86_64 (WSL2), headless.

## Issue description
In a coroutine whose lambdas capture local variables, after `await` on another coroutine (here
`wait_until(pred, n)`, which returns `true` immediately without suspending when `pred` is already true), an
`if` whose body declares a local variable is skipped although its condition is true. Adding an unrelated line before
the `if` makes the body run. Storing the await result and printing the condition shows it evaluates to a
`GDScriptFunctionState` object; inlined in a bigger function the error "Cannot convert argument 1 from Object to bool"
appears. This suggests a stack-slot / temporary mix-up around the await result.

Not reproduced when: the predicate lambda captures nothing; the awaited call is `await get_tree().process_frame`;
there is no capturing lambda in the function.

## Minimal reproduction
```gdscript
func wait_until(pred: Callable, frames: int) -> bool:
	for i in frames:
		if pred.call():
			return true
		await get_tree().process_frame
	return pred.call()

func repro() -> void:
	var a := 1
	var arr: Array = []
	var cb := func() -> void: arr.append([a, 2])
	cb.call()
	cb.call()
	var first: int = arr[0][0]
	await wait_until(func() -> bool: return Engine.get_process_frames() >= first, 5)
	if arr.size() >= 2:
		var gap := int(arr[1][0]) - first
		print("body ran ", gap)   # expected; never printed
	print("end")
```
Expected: "body ran 0" then "end". Actual: only "end".
(Before filing, the human should confirm this standalone version reproduces outside the project's test runner.)

## Impact
Tests silently pass without asserting. Workaround: move post-await conditionals into a non-coroutine helper.
