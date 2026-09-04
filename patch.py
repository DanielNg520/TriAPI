import re

def update_cmd_plan(file_path):
    with open(file_path, "r") as f:
        content = f.read()

    replacement = """
        if reply.lower() in APPROVE_WORDS:
            if "- [ ] " not in turn["text"]:
                print(
                    "\\nRefusing to approve: this response does not look like a plan "
                    "(it contains no '- [ ] ' checklist steps). If it is a clarifying "
                    "question, please answer it instead of approving."
                )
                # DO NOT append to history or send 'approve' back to the model.
                # Just ask the user again for real input.
                while True:
                    try:
                        reply = input("Your answer/feedback (or 'cancel'): ").strip()
                    except EOFError:
                        print("\\nNo input available. Aborting.")
                        state["status"] = "failed"
                        dispatcher.save_run(state)
                        return
                    if reply.lower() in APPROVE_WORDS:
                        print("Still cannot approve a non-plan. Please provide feedback or 'cancel'.")
                        continue
                    break
                
                if reply.lower() in CANCEL_WORDS:
                    state["status"] = "cancelled"
                    dispatcher.save_run(state)
                    log.info("[%s] Plan cancelled by user", state["run_id"])
                    print("Cancelled.")
                    return
                
                # Treat as feedback
                history.append({"user": message, "assistant": turn["text"]})
                message = reply
                print()
                continue

            state["plan_text"] = turn["text"]
            state["status"] = "planned"
"""
    
    pattern = r"""\n        if reply\.lower\(\) in APPROVE_WORDS:
            state\["plan_text"\] = turn\["text"\]
            state\["status"\] = "planned\""""

    new_content = re.sub(pattern, replacement, content)
    
    with open(file_path, "w") as f:
        f.write(new_content)

update_cmd_plan("scripts/triapi.py")
