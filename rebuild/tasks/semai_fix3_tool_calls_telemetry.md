In `src/semai/agent.py`'s `Agent.run()`, every `AgentResult(...)` construction reports `tool_calls` from the wrong source — either a local `tool_calls` variable that's empty at that point in the control flow, or only the LAST LLM response's tool_calls, not the accumulated history. The instance already tracks every tool actually called, in order, across the whole run: `self._called_names: list[str]` (appended to in `_dispatch()` for both read and propose paths).

Bug impact: a caller inspecting `AgentResult.tool_calls` sees `[]` even when tools were dispatched successfully on earlier steps in the same run — this hid a real production bug for a long time.

Fix: in every `AgentResult(...)` call inside `run()`, replace whatever expression currently fills `tool_calls=` with `tool_calls=list(self._called_names)`. There are 5 such constructions in `run()` (timeout, llm_error, bad_response, answered/no-tool-calls, and the final max_steps return) — all 5 need this same change, no other change to any of them.

Reply with a single fenced python block containing the complete, corrected `run()` method (same signature, same body except every `tool_calls=` argument in every `AgentResult(...)` call is now `tool_calls=list(self._called_names)`). Do not change anything else in the method.

For reference, here is the current method:

```python
    async def run(
        self,
        prompt: str,
        *,
        system_extra: str = "",
        history=None,
        model: str | None = None,
    ) -> AgentResult:
        """Run the bounded tool‑calling conversation."""
        messages: list[dict[str, Any]] = []
        if history:
            for turn in history:
                messages.append(turn)

        # initial system message
        system_msg = _SYSTEM_PROMPT + "\n\n" + load_rules(self.settings) + _now_line(self.settings)
        if system_extra:
            system_msg += "\n\n" + system_extra
        messages.append({"role": "system", "content": system_msg})
        # user prompt
        messages.append({"role": "user", "content": prompt})
        self._original_prompt = prompt

        start_time = datetime.now()
        deadline = start_time + timedelta(seconds=self.settings.agent_timeout_s)

        for step in range(self.settings.agent_max_steps):
            if datetime.now() > deadline:
                return AgentResult(
                    answer="",
                    steps=step,
                    tool_calls=[],
                    proposals=list(self.proposals),
                    stopped_because="timeout",
                    evidence="\n".join(self._evidence),
                )
            # Call LLM
            try:
                raw = await asyncio.to_thread(
                    self.llm.chat_raw,
                    model or self.settings.ollama_model,
                    messages,
                    tools=self.tools(),
                    temperature=0.0,
                )
            except Exception as e:
                return AgentResult(
                    answer=f"ERROR: LLM call failed: {e}",
                    steps=step,
                    tool_calls=[],
                    proposals=list(self.proposals),
                    stopped_because="llm_error",
                    evidence="\n".join(self._evidence),
                )

            # Expect a single assistant message
            if not raw or "content" not in raw:
                return AgentResult(
                    answer="ERROR: no content from LLM",
                    steps=step,
                    tool_calls=[],
                    proposals=list(self.proposals),
                    stopped_because="bad_response",
                    evidence="\n".join(self._evidence),
                )
            messages.append({"role": "assistant", "content": raw["content"]})

            # Process any tool calls
            tool_calls = raw.get("tool_calls") or []
            if not tool_calls:
                return AgentResult(
                    answer=raw["content"],
                    steps=step + 1,
                    tool_calls=[c.get("name") for c in tool_calls],
                    proposals=list(self.proposals),
                    stopped_because="answered",
                    evidence="\n".join(self._evidence),
                )

            # Resolve each tool call
            for tc in tool_calls:
                fn = tc.get("function") or tc
                name = fn.get("name")
                if not name or name in self._called:
                    continue  # duplicate or unknown

                try:
                    args = fn.get("arguments", {})
                    if isinstance(args, str):
                        import json
                        args = json.loads(args)
                    elif not isinstance(args, dict):
                        args = {}
                except Exception:
                    args = {}

                output = await asyncio.to_thread(self._dispatch, name, args)
                # Append tool result to history
                messages.append({"role": "tool", "name": name, "content": output})
                self._called.add(name)

            # Continue loop after processing tools

        return AgentResult(
            answer="",
            steps=self.settings.agent_max_steps,
            tool_calls=[c.get("name") for c in raw.get("tool_calls", [])],
            proposals=list(self.proposals),
            stopped_because="max_steps",
            evidence="\n".join(self._evidence),
        )
```
