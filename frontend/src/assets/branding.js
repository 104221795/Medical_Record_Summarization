import logoUrl from "../../icons_pic/logo.png";
import imageOne from "../../icons_pic/1.jpg";
import imageTwo from "../../icons_pic/2.jpg";
import imageThree from "../../icons_pic/3.jpg";
import imageFour from "../../icons_pic/4.png";

export const brandAssets = {
  logo: logoUrl,
  images: [imageOne, imageTwo, imageThree, imageFour],
};

export function applyDocumentBranding() {
  document.title = "Medical Record Summarization";
  let icon = document.querySelector("link[rel='icon']");
  if (!icon) {
    icon = document.createElement("link");
    icon.rel = "icon";
    document.head.appendChild(icon);
  }
  icon.href = logoUrl;
}
