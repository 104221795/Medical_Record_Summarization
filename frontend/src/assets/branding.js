import logoUrl from "../../icons_pic/logo.png";
import imageOne from "../../icons_pic/6.jpg";
import imageTwo from "../../icons_pic/2.jpg";
import imageThree from "../../icons_pic/3.jpg";
import imageFour from "../../icons_pic/5.jpg";
import aboutMedical from "../../icons_pic/medical.jpg";

export const brandAssets = {
  logo: logoUrl,
  images: [imageOne, imageTwo, imageThree, imageFour],
  aboutHero: aboutMedical,
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
