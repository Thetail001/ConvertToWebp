# 视频转 WebP 动图工具

一个视频转 WebP 动图的桌面小工具，支持自定义文本水印。

![应用截图](https://raw.githubusercontent.com/your-username/your-repo-name/main/screenshot.png) 
*(提示：请将上面的截图链接替换为您自己的实际截图URL)*

## 主要功能特点

- **视频转 WebP 动图**: 方便地将常见视频格式（如 MP4, MOV, AVI, MKV 等）转换为高质量的 WebP 动图。
- **灵活的水印设置**:
    - **文字定制**: 可自行输入水印文本内容。
    - **字体与颜色**: 支持选择本地字体文件（.ttf/.otf）及自定义水印颜色。
    - **透明度调节**: 轻松调整水印的显示透明度。
    - **位置选择**: 提供多种水印位置选项（左上、右下、居中等）。
    - **自适应大小**: 水印大小可根据视频分辨率按比例调整，力求最佳视觉效果。
    - **实时预览**: 在转换前，您可以直观地在界面上预览水印效果。
- **便捷的输出控制**:
    - **自定义文件名**: 可使用 `{name}` (原文件名) 和 `{time}` (当前时间) 等占位符来灵活命名输出文件。
    - **输出目录**: 自由选择 WebP 动图的保存位置。
    - **帧率调节**: 可设定输出 WebP 动图的帧率（FPS）。
- **优化用户体验**:
    - **拖拽操作**: 支持将视频文件直接拖拽至指定区域进行加载。
    - **高DPI适配**: 在 4K 等高分辨率屏幕上，界面和字体显示应会更加友好。
    - **异步转换**: 视频转换过程在后台进行，界面不会卡顿，您可以继续操作。

## ⚙️ 运行前准备：FFmpeg

本工具的视频处理功能需要依赖 **FFmpeg** 这个强大的多媒体工具。因此，在您运行本程序之前，请务必确保您的计算机上已安装并配置好 FFmpeg。

1.  **获取 FFmpeg**:
    *   您可以访问 FFmpeg 官方网站下载：[ffmpeg.org/download.html](https://ffmpeg.org/download.html)
    *   对于 Windows 用户，通常会从以下第三方网站下载预编译好的版本，操作更为简便：
        *   [gyan.dev/ffmpeg/builds](https://gyan.dev/ffmpeg/builds/) (建议选择 `essentials` 或 `full` 版本)
        *   [BtbN/FFmpeg-Builds/releases](https://github.com/BtbN/FFmpeg-Builds/releases)

2.  **配置 FFmpeg**:
    *   **推荐方式**: 将您下载的 FFmpeg 压缩包解压后，找到其中 `bin` 目录下的 `ffmpeg.exe` 和 `ffprobe.exe` 文件。**将这两个文件复制到本程序的可执行文件 (`.exe`) 所在的文件夹**（或 `main.py` 文件所在的目录），工具即可自动识别。
    *   **备用方式**: 如果您希望全局使用 FFmpeg，可以将 `ffmpeg.exe` 和 `ffprobe.exe` 所在的 `bin` 目录路径添加到您操作系统的**环境变量 `PATH`** 中。

## 如何使用

### 方式一：下载可执行文件 (.exe) 使用 (推荐)

1.  **下载 Release 包**: 前往项目的 GitHub Release 页面，下载最新的 `ConvertToWebp.exe` 文件。
2.  **配置 FFmpeg**: 按照上方“运行前准备：FFmpeg”中的说明，将 `ffmpeg.exe` 和 `ffprobe.exe` 放置在与 `ConvertToWebp.exe` 同一目录下。
3.  **运行**: 双击 `ConvertToWebp.exe` 即可启动程序。

### 方式二：从源代码运行 (适用于开发者)

1.  **克隆项目**:
    ```bash
    git clone https://github.com/your-username/your-repo-name.git
    cd your-repo-name
    ```
    *(提示：请将上面的 URL 替换为您自己的实际仓库地址)*

2.  **安装 Python 依赖**:
    建议在虚拟环境中安装：
    ```bash
    pip install -r requirements.txt
    ```

3.  **配置 FFmpeg**: 按照上方“运行前准备：FFmpeg”中的说明，将 `ffmpeg.exe` 和 `ffprobe.exe` 放置在与 `main.py` 同一目录下，或者添加到系统 `PATH`。

4.  **运行程序**:
    ```bash
    python main.py
    ```

## 使用流程概览

1.  **载入视频**: 通过拖拽视频文件或点击选择，将您的视频载入程序。
2.  **调整水印**: 在界面左侧的“水印设置”区，根据您的需要调整水印的文本、样式、位置和大小。实时预览功能会帮助您看到效果。
3.  **设定输出**: 在“输出设置”区，您可以指定最终 WebP 文件的保存路径、命名规则和帧率。
4.  **开始转换**: 点击“开始转换”按钮，程序将处理您的视频并生成带有水印的 WebP 动图。
5.  **查看结果**: 转换完成后，您可以在右侧预览区查看生成的 WebP 文件，并可选择打开输出文件夹。
