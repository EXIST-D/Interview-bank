"""Validate syntax, Markdown links/examples, packaged install and readonly skill."""
import ast
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/interview-bank"
sys.path.insert(0, str(SKILL / "scripts"))
from ibank_core import __version__


def tree_hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


def tracked(paths):
    """Only check documents that belong to the repository, not untracked local notes."""
    listing = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True)
    if listing.returncode:
        return list(paths)
    names = {name.decode("utf-8") for name in listing.stdout.split(b"\0") if name}
    return [p for p in paths if p.relative_to(ROOT).as_posix() in names]


def main():
    count = 0
    for directory in (SKILL, ROOT / "tools", ROOT / "tests"):
        for path in directory.rglob("*.py"):
            ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
            count += 1
    for path in [ROOT / "README.md", ROOT / "README.en.md", *SKILL.rglob("*.md"), *tracked(ROOT.glob("*.md")), *tracked(ROOT.glob("docs/*.md"))]:
        body = path.read_text(encoding="utf-8")
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", body):
            if "://" not in target and not target.startswith("#"):
                assert (path.parent / target.split("#")[0]).exists(), (path, target)
        for block in re.findall(r"```json\s*\n(.*?)\n```", body, re.S):
            json.loads(block)
    archive = ROOT / f"dist/interview-bank-{__version__}.zip"
    work = (ROOT / ".work/package-checks").resolve()
    assert work.is_relative_to(ROOT)
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=work) as temp:
        directory = Path(temp)
        with zipfile.ZipFile(archive) as zipin:
            for name in zipin.namelist():
                assert (directory / name).resolve().is_relative_to(directory)
                assert name.startswith("interview-bank/")
            zipin.extractall(directory)
        installed = directory / "interview-bank"
        before = tree_hashes(installed)
        bank = directory / "sample-bank"
        cli = installed / "scripts/ibank.py"
        def run(*arguments):
            result = subprocess.run([sys.executable, "-B", str(cli), *arguments, "--bank", str(bank), "--json"],
                                    capture_output=True, text=True, encoding="utf-8", cwd=directory)
            assert result.returncode == 0, result.stderr
            return json.loads(result.stdout)["result"]
        run("init")
        selected = directory / "selected.txt"
        selected.write_text("Redis 为什么快？\n", encoding="utf-8")
        stage = run("stage", "--text", str(selected), "--role", "backend", "--technology", "redis")
        run("commit", "--run", stage["run_id"])
        assert run("search", "--technology", "redis")["total"] == 1
        run("export", "--format", "markdown", "--output", "review.md")
        run("research", "--limit", "1")
        assert run("migrate", "plan")["from_version"] == 1
        assert run("migrate", "apply")["upgraded"]
        serial = 0
        def payload_run(command, action, payload=None, key=None):
            nonlocal serial
            arguments = [command, action]
            if payload is not None:
                serial += 1
                path = directory / f"input-{serial}.json"
                path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
                arguments.extend(["--input", str(path)])
            if key: arguments.extend(["--id", key])
            return run(*arguments)
        def committed(result):
            if "run_id" in result: run("commit", "--run", result["run_id"])
            return result.get("summary", result)
        qid = run("search", "--technology", "redis")["questions"][0]["id"]
        committed(payload_run("policy", "add", {"kind":"protect", "question_id":qid, "field":"canonical", "reason":"Installation fixture", "user_requested":True, "user_quote":"Synthetic: keep this wording"}))
        topic = committed(payload_run("studyset", "create", {"name":"安装验收专题", "expression":{"field":"technology","values":["redis"]}}))["studyset_id"]
        run("studyset", "export", "--id", topic, "--output", "topic.md")
        flow = committed(payload_run("workflow", "create", {"name":"安装验收研究", "studyset_id":topic}))["workflow_id"]
        packet = run("workflow", "next", "--id", flow)
        assert len(packet["task"]["items"]) == 1
        committed(payload_run("workflow", "block", {"question_id":qid,"reason":"Synthetic smoke does not claim live research"}, flow))
        assert run("workflow", "show", "--id", flow)["status"] == "blocked"
        committed(payload_run("workflow", "resume", {"retry_blocked":True}, flow))
        assert run("workflow", "show", "--id", flow)["remaining"] == 1
        run("workflow", "summary", "--id", flow)
        session = committed(payload_run("interview", "start", {"name":"Synthetic installation interview", "studyset_id":topic}))["session_id"]
        assert "reference_answer" not in run("interview", "next", "--id", session)
        answer = {"question_id":qid,"request_id":"smoke-answer","text":"内存访问。"}
        committed(payload_run("interview", "answer", answer, session))
        pending = run("interview", "next", "--id", session)
        committed(payload_run("interview", "feedback", {"response_id":pending["response"]["id"], "limited_basis":True, "observations":[{"dimension":"coverage","quote":"内存","note":"Synthetic limited feedback"}]}, session))
        committed(payload_run("interview", "end", key=session))
        assert run("interview", "summary", "--id", session)["status"] == "completed"
        assert payload_run("interview", "answer", answer, session)["already_recorded"]
        practice = {"question_id":qid,"session_id":session,"request_id":"smoke-event","rating":"good","note":"Synthetic self-rating fixture","user_quote":"Synthetic: I know this one"}
        committed(payload_run("study", "record", practice))
        assert payload_run("study", "record", practice)["already_recorded"]
        assert len(payload_run("study", "queue", {"include_future":True})["questions"]) == 1
        assert run("evidence", "list")["evidence"] == []
        subtitle = directory / "provided.srt"
        subtitle.write_text("1\n00:00:01,000 --> 00:00:02,500\n数据库索引是什么？\n", encoding="utf-8")
        intake = run("media", str(subtitle), "--retention", "copy")
        sid = intake["items"][0]["source_id"]
        assert run("media-task", "--run", intake["id"], "--source", sid)["segments"][0]["start"] == 1
        response = directory / "media-extracted.json"
        response.write_text(json.dumps({"schema_version":1,"sources":[{"source_id":sid,"status":"extracted","reviewed_segment_ids":[1],
            "questions":[{"id":"media-smoke","sequence":1,"original_text":"数据库索引是什么？","segment_ids":[1],"reviewed":True,
                          "confidence":{"is_question":1,"classification":1}}]}]}, ensure_ascii=False), encoding="utf-8")
        run("extract-save", "--run", intake["id"], "--input", str(response))
        staged_media = run("stage", "--from-intake", intake["id"])
        run("commit", "--run", staged_media["run_id"])
        exported_media = run("export", "--output", "media.md")
        details = json.loads(Path(exported_media["details_output"]).read_text(encoding="utf-8"))
        assert any("locator" in o for q in details["questions"] for o in q["occurrences"])
        assert run("media", str(subtitle))["items"] == []
        assert run("doctor")["media_intakes"] == []
        capabilities = run("capabilities", "--workspace", str(directory))
        assert capabilities["workspace_writable"] and not capabilities["network_request_performed"]
        host_profile = {"schema_version":1,"name":"Synthetic package host","transcription":{
            "tool":"fixture.transcribe","provider":"fixture","execution":"local","destination":None,"evidence":"Synthetic contract fixture"}}
        profile_path = directory / "host-profile.json"
        profile_path.write_text(json.dumps(host_profile),encoding="utf-8")
        raw = directory / "fixture.wav"
        raw.write_bytes(b"adapter contract fixture, not actual audio")
        host_intake = run("media", str(raw))
        host_sid = host_intake["items"][0]["source_id"]
        assert run("media-plan", "--run", host_intake["id"], "--host-profile", str(profile_path))["items"][0]["route"] == "host"
        packet = run("media-provider-task", "--run", host_intake["id"], "--source", host_sid, "--host-profile", str(profile_path))
        host_response = directory / "host-result.json"
        host_response.write_text(json.dumps({"schema_version":1,"task_id":packet["id"],"source_sha256":packet["source_sha256"],
            "provider":packet["provider"],"format":"chunks","result":{"chunks":[{"timestamp":[1,2],"text":"数据库索引是什么？"}]}},ensure_ascii=False),encoding="utf-8")
        run("media-provider-import", "--run", host_intake["id"], "--input", str(host_response))
        assert run("media-provider-import", "--run", host_intake["id"], "--input", str(host_response))["already_imported"]
        assert run("media-task", "--run", host_intake["id"], "--source", host_sid)["segments"][0]["start"] == 1
        assert run("taxonomy", "--dimension", "domains", "--query", "向量")["items"][0]["id"] == "backend.database.vector"
        assert run("validate")["valid"]
        assert not run("doctor")["incomplete_runs"]
        demo = subprocess.run([sys.executable, "-B", str(cli), "demo", "--bank", str(directory / "demo-bank"), "--json"],
                              capture_output=True, text=True, encoding="utf-8", cwd=directory)
        assert demo.returncode == 0 and json.loads(demo.stdout)["result"]["answered"] == 8, demo.stderr
        backup = run("backup", "create")
        assert run("backup", "verify", "--archive", backup["archive"])["valid"]
        restored = run("backup", "restore", "--archive", backup["archive"], "--destination", str(directory / "restored-bank"))
        assert Path(restored["restored_bank"]).joinpath("manifest.json").is_file()
        # Launch the unpacked optional UI, verify its bundled assets and actual API.
        import urllib.request
        process = subprocess.Popen([sys.executable, "-B", str(cli), "web", "--bank", str(bank), "--read-only", "--json"],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", cwd=directory)
        try:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=1) as executor:
                ready = executor.submit(process.stdout.readline)
                try:
                    line = ready.result(timeout=15)
                except TimeoutError:
                    process.terminate()
                    raise AssertionError("Packaged Web did not become ready")
            launch = json.loads(line)["result"]["url"]
            origin, token = launch.split('/#token=')
            for route, expected in (("/", b"Interview Bank"), ("/app.js", b"saveRating"), ("/app.css", b"--canvas")):
                with urllib.request.urlopen(origin+route, timeout=5) as response:
                    assert expected in response.read()
            request = urllib.request.Request(origin+'/api/library', headers={'X-Interview-Token':token})
            with urllib.request.urlopen(request, timeout=5) as response:
                library = json.load(response)
                assert library['total'] == 2 and library['read_only'] and not library['can_record']
        finally:
            process.terminate()
            process.communicate(timeout=10)
        assert before == tree_hashes(installed), "Installed skill was modified"
    print(json.dumps({"python_files_parsed": count, "markdown_links_and_json": "passed", "packaged_cli_smoke": "passed", "packaged_media_smoke": "passed", "packaged_host_adapter": "passed", "packaged_web": "passed", "packaged_backup": "passed", "readonly_install": "passed"}))


if __name__ == "__main__":
    main()
