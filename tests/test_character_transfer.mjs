import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("../web/character_transfer.js", import.meta.url), "utf8")
  .replace(/^import .*;\r?\n/gm, "");

async function setup(name, fetchApi) {
  let extension;
  const elements = [];
  const alerts = [];
  const document = {
    createElement(type) {
      const element = { type, click() { this.clicked = true; }, remove() { this.removed = true; } };
      elements.push(element);
      return element;
    },
    body: { appendChild() {} },
  };
  vm.runInNewContext(source, {
    app: { registerExtension(value) { extension = value; } },
    api: { fetchApi, apiURL: (path) => `/proxy${path}` },
    document, FormData, alert: (message) => alerts.push(message),
  });
  class Node {
    constructor() {
      this.widgets = [{ name: "filename", value: "" }, { name: "upload_id", value: "" }];
    }
    addWidget(type, name, value, callback, options) {
      const widget = { type, name, value, callback, options };
      this.widgets.push(widget);
      return widget;
    }
    setDirtyCanvas() {}
    setSize() {}
    computeSize() { return [300, 150]; }
  }
  await extension.beforeRegisterNodeDef(Node, { name });
  const node = new Node();
  node.onNodeCreated();
  return { node, elements, alerts };
}

test("upload opens file picker and persists the returned file reference", async () => {
  const { node, elements } = await setup("OmnicharLoadCharacterExternal", async (url, options) => {
    assert.equal(url, "/omnichar/upload");
    assert.equal(options.method, "POST");
    assert.equal(options.body.get("file").name, "Ada.char");
    return { ok: true, json: async () => ({ filename: "Ada.char", upload_id: "a".repeat(32) }) };
  });
  const button = node.widgets.at(-1);
  button.callback();
  assert.equal(elements[0].accept, ".char");
  assert.equal(elements[0].clicked, true);
  elements[0].files = [new File(["char data"], "Ada.char")];
  await elements[0].onchange();
  assert.equal(node.widgets[0].value, "Ada.char");
  assert.equal(node.widgets[1].value, "a".repeat(32));
  assert.equal(button.name, "choose file to upload");
  assert.equal(node.omnicharUploading, false);
});

test("failed upload retains the previous character and reports the error", async () => {
  const { node, elements, alerts } = await setup("OmnicharLoadCharacterExternal", async () => ({
    ok: false, status: 413, text: async () => "too large",
  }));
  node.widgets[0].value = "previous.char";
  node.widgets.at(-1).callback();
  elements[0].files = [new File(["char"], "Ada.char")];
  await elements[0].onchange();
  assert.equal(node.widgets[0].value, "previous.char");
  assert.match(alerts[0], /upload size limit/);
  assert.equal(node.omnicharUploading, false);
});

test("download is available after execution and uses the browser download", async () => {
  const { node, elements, alerts } = await setup("OmnicharSaveCharacterExternal", async (url, options) => {
    assert.equal(options.method, "HEAD");
    return { ok: true };
  });
  const button = node.widgets.at(-1);
  await button.callback();
  assert.equal(elements.length, 0);
  assert.match(alerts[0], /Run the workflow/);
  node.onExecuted({ omnichar_download: [{ id: "a".repeat(32), filename: "Ada.char" }] });
  assert.equal(button.name, "download character");
  await button.callback();
  assert.equal(elements[0].download, "Ada.char");
  assert.equal(elements[0].href, `/proxy/omnichar/download/${"a".repeat(32)}/Ada.char`);
  assert.equal(elements[0].clicked, true);
  assert.equal(elements[0].removed, true);
});

test("expired download asks for another run", async () => {
  const { node, elements, alerts } = await setup("OmnicharSaveCharacterExternal", async () => ({ ok: false }));
  node.onExecuted({ omnichar_download: [{ id: "a".repeat(32), filename: "Ada.char" }] });
  await node.widgets.at(-1).callback();
  assert.equal(elements.length, 0);
  assert.match(alerts[0], /Run the workflow again/);
});
