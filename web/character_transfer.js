import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

app.registerExtension({
  name: "omnichar.characterTransfer",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    const upload = nodeData.name === "OmnicharLoadCharacterExternal";
    const download = nodeData.name === "OmnicharSaveCharacterExternal";
    if (!upload && !download) return;

    const onCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const result = onCreated?.apply(this, arguments);
      if (upload) {
        const filename = this.widgets.find((widget) => widget.name === "filename");
        const uploadId = this.widgets.find((widget) => widget.name === "upload_id");
        filename.options = { ...filename.options, readOnly: true };
        // Keep the identifier in saved workflows, but show only the chosen filename.
        uploadId.type = "hidden";
        uploadId.computeSize = () => [0, -4];
        const button = this.addWidget("button", "choose file to upload", null, () => {
          if (this.omnicharUploading) return;
          const input = document.createElement("input");
          input.type = "file";
          input.accept = ".char";
          input.onchange = async () => {
            const file = input.files?.[0];
            if (!file) return;
            this.omnicharUploading = true;
            button.name = "uploading character...";
            this.setDirtyCanvas(true, true);
            try {
              const body = new FormData();
              body.append("file", file);
              const response = await api.fetchApi("/omnichar/upload", { method: "POST", body });
              if (!response.ok) {
                const message = await response.text();
                throw new Error(response.status === 413
                  ? "Character exceeds the ComfyUI upload size limit."
                  : message || `Upload failed (${response.status}).`);
              }
              const uploaded = await response.json();
              filename.value = uploaded.filename;
              uploadId.value = uploaded.upload_id;
              filename.callback?.(filename.value);
              uploadId.callback?.(uploadId.value);
              this.omnicharRefreshPreview();
            } catch (error) {
              alert(`Character upload failed: ${error.message}`);
            } finally {
              this.omnicharUploading = false;
              button.name = "choose file to upload";
              this.setDirtyCanvas(true, true);
            }
          };
          input.click();
        }, { serialize: false });
        let previewImage = null;
        let previewRequest = 0;
        this.addCustomWidget({
          name: "character_preview",
          type: "omnichar_preview",
          options: { serialize: false },
          computeSize: () => [0, previewImage ? 228 : 0],
          draw: (ctx, node, width, y) => {
            if (!previewImage) return;
            const scale = Math.min((width - 20) / previewImage.width, 216 / previewImage.height);
            const w = previewImage.width * scale;
            const h = previewImage.height * scale;
            ctx.drawImage(previewImage, (width - w) / 2, y + 4, w, h);
          },
        });
        this.omnicharRefreshPreview = () => {
          const request = ++previewRequest;
          previewImage = null;
          this.setSize(this.computeSize());
          this.setDirtyCanvas(true, true);
          if (!filename.value || !uploadId.value) return;
          const image = new Image();
          image.onload = () => {
            if (request !== previewRequest) return;
            previewImage = image;
            this.setSize(this.computeSize());
            this.setDirtyCanvas(true, true);
          };
          image.src = api.apiURL(`/omnichar/preview/${encodeURIComponent(uploadId.value)}/${encodeURIComponent(filename.value)}`);
        };
      } else {
        this.omnicharDownloadButton = this.addWidget(
          "button", "run workflow to prepare download", null, async () => {
            const file = this.omnicharDownload;
            if (!file) {
              alert("Run the workflow first to prepare the character download.");
              return;
            }
            const route = `/omnichar/download/${encodeURIComponent(file.id)}/${encodeURIComponent(file.filename)}`;
            try {
              // Check expiry first, then let the browser stream the download to disk.
              const response = await api.fetchApi(route, { method: "HEAD" });
              if (!response.ok) throw new Error("Download unavailable. Run the workflow again.");
              const link = document.createElement("a");
              link.href = api.apiURL(route);
              link.download = file.filename;
              document.body.appendChild(link);
              link.click();
              link.remove();
            } catch (error) {
              alert(error.message);
            }
          }, { serialize: false }
        );
      }
      this.setSize(this.computeSize());
      return result;
    };

    if (upload) {
      const onConfigure = nodeType.prototype.onConfigure;
      nodeType.prototype.onConfigure = function () {
        const result = onConfigure?.apply(this, arguments);
        this.omnicharRefreshPreview?.();
        return result;
      };
    }

    if (download) {
      const onExecuted = nodeType.prototype.onExecuted;
      nodeType.prototype.onExecuted = function (message) {
        const result = onExecuted?.apply(this, arguments);
        this.omnicharDownload = message?.omnichar_download?.[0] ?? null;
        if (this.omnicharDownloadButton) {
          this.omnicharDownloadButton.name = this.omnicharDownload
            ? "download character"
            : "run workflow to prepare download";
        }
        this.setDirtyCanvas(true, true);
        return result;
      };
    }
  },
});
