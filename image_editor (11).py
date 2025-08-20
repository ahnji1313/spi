"""
Image Editor Program
====================

This script implements a simple yet powerful image editing application
using Python's built‑in ``tkinter`` GUI toolkit and the `Pillow`
library (also known as PIL).  It provides many of the fundamental
features you would expect from a desktop image editor, including

* **Layers** — load images or create blank canvases as layers that
  can be stacked, reordered, shown/hidden, merged or deleted.
* **Brush** — freehand drawing on any layer with adjustable colour and
  size.  Drawing strokes are committed directly to the selected
  layer.
* **Filters** — apply common filters such as grayscale, invert,
  blur and sharpen to the selected layer.
* **Adjustments** — modify layer properties like transparency (alpha)
  and brightness using sliders.
* **Text** — add text labels to layers by clicking on the image and
  specifying the content, font size and colour.
* **File operations** — open existing images as layers and save the
  composite result of all visible layers to disk.

The application is designed to be straightforward to use while still
showing how to orchestrate multiple image operations in an object
oriented fashion.  Each layer holds both its original image and a
modifiable working copy so that adjustments and filters can be applied
without losing the ability to revert or re‑apply operations.  The
main canvas always displays a composited preview of all visible layers.

Prerequisites
-------------

Before running this program, you must install the Pillow library, which
adds advanced image processing capabilities to Python.  You can
install it with pip:

```
pip install pillow
```

The built in `tkinter` module is used for the GUI, so there are no
additional dependencies.  On most systems Tkinter comes bundled with
Python; if not, consult your platform's documentation on how to
enable Tk support.

Usage
-----

Run this file with Python (`python3 image_editor.py`) and a window
will open.  Use the menu bar at the top to load images, create new
layers, select tools (brush, text), apply filters and adjustments,
toggle layer visibility and save your work.  The current layer can
be changed via the layer list at the left of the window.

This implementation is intentionally kept self contained for easy
review and extension.  Feel free to explore the code, learn how it
works and add your own features!

This example demonstrates that building an image editor in Python is
feasible using Tkinter and Pillow.  In fact, tutorials like the one
on GeeksforGeeks show how to combine these libraries to perform
operations such as opening images, resizing, blurring, flipping and
rotating【182082927575283†L82-L104】.  The program here builds on those
concepts to provide a multi‑layer editing environment with drawing and
filter capabilities.
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, colorchooser
from tkinter import ttk
from PIL import Image, ImageTk, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageChops
import math

# ----------------------------------------------------------------------
# Image utility functions
# ----------------------------------------------------------------------
def swirl_image(img: Image.Image, center: tuple[int, int] | None = None, strength: float = 4.0, radius: float | None = None) -> Image.Image:
    """Apply a swirl (liquify) effect to the image.

    This effect warps pixels around the centre point.  Pixels closer to
    the centre are rotated more than those further away, creating a
    whirlpool effect reminiscent of liquify tools in professional
    editors.  The algorithm iterates over the output image and
    computes source coordinates in the input image using polar
    coordinates.

    :param img: input PIL image (RGBA).
    :param center: optional (x, y) centre of swirl; defaults to image
        centre.
    :param strength: controls the amount of rotation (higher values
        produce a stronger swirl).
    :param radius: maximum distance from centre affected; defaults
        to half the minimum dimension.
    :returns: new PIL image with swirl effect applied.
    """
    width, height = img.size
    if center is None:
        cx, cy = width / 2.0, height / 2.0
    else:
        cx, cy = center
    if radius is None:
        radius = min(width, height) / 2.0
    # Prepare pixel access
    src_pixels = img.load()
    result = Image.new("RGBA", img.size)
    dst_pixels = result.load()
    for y in range(height):
        for x in range(width):
            dx = x - cx
            dy = y - cy
            r = math.hypot(dx, dy)
            if r < 1:
                # very close to centre; no change
                nx, ny = x, y
            else:
                if r > radius:
                    # outside swirl radius: unchanged
                    nx, ny = x, y
                else:
                    # compute angle and apply swirl
                    theta = math.atan2(dy, dx)
                    factor = 1 - (r / radius)
                    angle = strength * factor
                    new_theta = theta + angle
                    nx = cx + r * math.cos(new_theta)
                    ny = cy + r * math.sin(new_theta)
            ix = int(nx)
            iy = int(ny)
            if 0 <= ix < width and 0 <= iy < height:
                dst_pixels[x, y] = src_pixels[ix, iy]
            else:
                dst_pixels[x, y] = (0, 0, 0, 0)
    return result


class Layer:
    """Represents a single editable image layer.

    Each layer stores both its original unmodified image and a working
    image.  Filters and adjustments (brightness, contrast, colour and
    transparency) are applied to the working copy so that changes are
    non‑destructive — the original can be used as the base for
    reapplying operations if needed.
    """

    def __init__(self, image: Image.Image, name: str):
        # Always store images in RGBA mode to support transparency
        self.original = image.convert("RGBA")
        self.image = self.original.copy()
        self.name = name
        self.visible = True
        # adjustment factors
        self.alpha: float = 1.0
        self.brightness: float = 1.0
        self.contrast: float = 1.0
        self.color: float = 1.0  # colour (saturation) factor
        # gamma (exposure) adjustment; 1.0 means no change
        self.gamma: float = 1.0
        # positional offset (dx, dy) for moving the layer
        self.offset = (0, 0)
        # mask for non‑destructive hiding/revealing of pixels
        self.mask = Image.new("L", self.original.size, 255)
        # blending mode: 'normal' or 'multiply'
        self.blend_mode: str = 'normal'
        # Channel factors for selective colour adjustments
        # Multipliers for red, green and blue channels respectively. 1.0 means no change.
        self.red: float = 1.0
        self.green: float = 1.0
        self.blue: float = 1.0

    def apply_adjustments(self) -> None:
        """Reapply brightness, contrast, colour and alpha adjustments.

        The working copy is reset to the original and then brightness,
        contrast and colour enhancements are applied in sequence.  Finally
        the alpha channel is scaled.  Calling this after any change
        ensures the displayed image reflects the current adjustment
        settings.
        """
        # Start from original
        self.image = self.original.copy()
        # Apply brightness
        if self.brightness != 1.0:
            enhancer = ImageEnhance.Brightness(self.image)
            self.image = enhancer.enhance(self.brightness)
        # Apply contrast
        if self.contrast != 1.0:
            enhancer = ImageEnhance.Contrast(self.image)
            self.image = enhancer.enhance(self.contrast)
        # Apply colour (saturation)
        if self.color != 1.0:
            enhancer = ImageEnhance.Color(self.image)
            self.image = enhancer.enhance(self.color)
        # Apply gamma (exposure)
        if self.gamma != 1.0:
            r, g, b, a = self.image.split()
            def apply_gamma(channel: Image.Image, gamma: float) -> Image.Image:
                return channel.point(lambda i: int((i / 255.0) ** (1.0 / gamma) * 255))
            r = apply_gamma(r, self.gamma)
            g = apply_gamma(g, self.gamma)
            b = apply_gamma(b, self.gamma)
            self.image = Image.merge("RGBA", (r, g, b, a))
        # Apply per channel (selective colour) adjustments
        if self.red != 1.0 or self.green != 1.0 or self.blue != 1.0:
            r, g, b, a = self.image.split()
            # Scale each channel by its factor and clip
            if self.red != 1.0:
                r = r.point(lambda i: int(min(255, i * self.red)))
            if self.green != 1.0:
                g = g.point(lambda i: int(min(255, i * self.green)))
            if self.blue != 1.0:
                b = b.point(lambda i: int(min(255, i * self.blue)))
            self.image = Image.merge("RGBA", (r, g, b, a))
        # Apply alpha transparency
        r, g, b, a = self.image.split()
        new_alpha = a.point(lambda i: int(i * self.alpha))
        # Combine with mask so that painted mask regions hide pixels
        combined_alpha = ImageChops.multiply(new_alpha, self.mask)
        self.image.putalpha(combined_alpha)

    def apply_filter(self, filter_name: str) -> None:
        """Apply a named filter to the original image and update working copy.

        Supported filters include: grayscale, invert, blur, sharpen,
        emboss, edge, contour, detail and smooth.  After applying
        the filter to the original image, adjustments are reapplied to
        update the working copy.
        """
        fname = filter_name.lower()
        if fname == "grayscale":
            gray = self.original.convert("L")
            self.original = Image.merge("RGBA", (gray, gray, gray, self.original.split()[3]))
        elif fname == "invert":
            r, g, b, a = self.original.split()
            inv_r = r.point(lambda i: 255 - i)
            inv_g = g.point(lambda i: 255 - i)
            inv_b = b.point(lambda i: 255 - i)
            self.original = Image.merge("RGBA", (inv_r, inv_g, inv_b, a))
        elif fname == "blur":
            self.original = self.original.filter(ImageFilter.GaussianBlur(radius=2))
        elif fname == "sharpen":
            self.original = self.original.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
        elif fname == "emboss":
            self.original = self.original.filter(ImageFilter.EMBOSS)
        elif fname == "edge":
            self.original = self.original.filter(ImageFilter.EDGE_ENHANCE)
        elif fname == "contour":
            self.original = self.original.filter(ImageFilter.CONTOUR)
        elif fname == "detail":
            self.original = self.original.filter(ImageFilter.DETAIL)
        elif fname == "smooth":
            self.original = self.original.filter(ImageFilter.SMOOTH_MORE)
        elif fname in ("liquify", "swirl"):
            # Apply swirl liquify effect around the centre
            self.original = swirl_image(self.original)
        elif fname == "sepia":
            # Apply a sepia tone to the image. This gives a warm, vintage look
            # by converting to grayscale and then mapping the channels to a
            # sepia palette. See: https://en.wikipedia.org/wiki/Sepia_(color)
            r, g, b, a = self.original.split()
            # Convert to grayscale
            gray = Image.merge("RGB", (r, g, b)).convert("L")
            # Create a sepia tinted image by applying custom matrix
            sepia = Image.new("RGBA", self.original.size)
            pixels = sepia.load()
            gray_pixels = gray.load()
            for j in range(self.original.height):
                for i in range(self.original.width):
                    val = gray_pixels[i, j]
                    # Apply sepia transformation: red=val*1.07, green=val*0.74, blue=val*0.43
                    # Clip to 255
                    sr = min(255, int(val * 1.07))
                    sg = min(255, int(val * 0.74))
                    sb = min(255, int(val * 0.43))
                    pixels[i, j] = (sr, sg, sb, a.getpixel((i, j)))
            self.original = sepia
        elif fname == "skin smooth" or fname == "skin_smooth":
            # Apply median blur to smooth skin while preserving edges to some degree.
            # This approximates frequency separation by reducing high frequency noise.
            self.original = self.original.filter(ImageFilter.MedianFilter(size=5))
        else:
            raise ValueError(f"Unsupported filter: {filter_name}")
        # After modifying the original image, reapply adjustments so that
        # the working copy reflects changes. Without this, the filtered
        # result may not appear on the canvas.
        self.apply_adjustments()

    def apply_filter_to_region(self, filter_name: str, box: tuple[int, int, int, int]) -> None:
        """Apply the specified filter only within the given bounding box on the original image.

        :param filter_name: one of the supported filter names (grayscale, invert, blur, etc.).
        :param box: tuple (left, upper, right, lower) specifying region in image coordinates.
        """
        # Ensure region is within bounds
        left, upper, right, lower = box
        left = max(0, left)
        upper = max(0, upper)
        right = min(self.original.width, right)
        lower = min(self.original.height, lower)
        if right <= left or lower <= upper:
            return
        # Crop region from original
        region = self.original.crop((left, upper, right, lower)).copy()
        # Create temporary layer to reuse existing filter implementation
        temp_layer = Layer(region, "temp")
        # Apply filter on temporary layer's original image
        try:
            temp_layer.apply_filter(filter_name)
        except Exception:
            return
        # Paste filtered region back into original
        self.original.paste(temp_layer.original, (left, upper))
        # Reapply adjustments to update working copy
        self.apply_adjustments()
        # After modifying original, apply adjustments to update working copy
        self.apply_adjustments()


class ImageEditor(tk.Tk):
    """Main application window for the image editor."""

    def __init__(self):
        super().__init__()
        self.title("Python Image Editor")
        # Set a larger default size (90% of screen) for the editing window
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        win_w = int(screen_w * 0.9)
        win_h = int(screen_h * 0.9)
        self.geometry(f"{win_w}x{win_h}")
        # Apply ttk theme for a more modern look
        style = ttk.Style(self)
        try:
            style.theme_use('clam')
        except Exception:
            pass
        # Use a very light neutral background for a softer feel
        self.configure(bg="#fafafa")

        # List of layers (bottom to top)
        self.layers: list[Layer] = []
        self.current_layer_index: int | None = None
        # History of document states for undo/redo
        self.history: list[dict] = []
        # index pointing to current position in history; -1 means no state saved yet
        self.history_index: int = -1
        # maximum number of states to keep in history (increased to 100)
        self.max_history: int = 100

        # Set up GUI components
        self._create_widgets()

        # Tool variables
        # current tool can be "brush", "text", "eraser" or None
        self.current_tool = None
        self.brush_color = "#ff0000"
        self.brush_size = 5

        # Flag to avoid saving multiple history states during a continuous stroke
        self._history_saved_for_stroke = False

        # For drawing operations
        self._drag_prev = None
        # Variables for filter region selection
        self._filter_region_start = None
        self._filter_rect_id = None

        # Directory for saving and loading drafts (local storage)
        # Use a folder in the user's home directory for persistence across sessions
        self.draft_dir = os.path.join(os.path.expanduser("~"), ".image_editor_drafts")
        # Create the directory if it does not exist
        try:
            os.makedirs(self.draft_dir, exist_ok=True)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # GUI construction
    # ------------------------------------------------------------------
    def _create_widgets(self):
        # Menu bar
        self._create_menus()

        # Define a soft colour palette for the UI
        # Define a soft pastel palette to produce a gentle, modern feel
        bg_panel = "#fafafa"        # panel backgrounds
        bg_toolbar = "#f3f3f3"      # toolbar backgrounds
        btn_bg = "#e6e6e6"         # button backgrounds
        btn_fg = "#333333"         # button text colour (dark grey)
        slider_bg = "#f0f0f0"      # slider background
        slider_fg = "#333333"       # slider text and ticks
        label_bg = bg_panel
        label_fg = "#333333"        # label text dark for contrast

        # Left frame for layer list and controls
        left_frame = tk.Frame(self, width=260, bg=bg_panel)
        left_frame.pack(side=tk.LEFT, fill=tk.Y)

        # Button to add new blank layer
        new_layer_btn = tk.Button(left_frame, text="New Layer", command=self._new_layer, bg=btn_bg, fg=btn_fg, relief=tk.RAISED, bd=1)
        new_layer_btn.pack(padx=8, pady=6, fill=tk.X)

        # Listbox to show layers
        self.layer_listbox = tk.Listbox(
            left_frame,
            selectmode=tk.SINGLE,
            font=("Arial", 11),
            bg="#ffffff",
            fg="#333333",
            activestyle='none',
            highlightthickness=1,
            borderwidth=1,
        )
        self.layer_listbox.pack(padx=8, pady=6, fill=tk.BOTH, expand=True)
        self.layer_listbox.bind('<<ListboxSelect>>', self._on_layer_select)
        # Bind double click to rename layer
        self.layer_listbox.bind('<Double-Button-1>', self._rename_layer)
        # Context menu for layers (right‑click)
        self.layer_menu = tk.Menu(self, tearoff=0)
        self.layer_menu.add_command(label="Duplicate", command=self._duplicate_layer)
        self.layer_menu.add_command(label="Delete", command=self._delete_layer)
        self.layer_menu.add_command(label="Move Up", command=lambda: self._move_layer(-1))
        self.layer_menu.add_command(label="Move Down", command=lambda: self._move_layer(1))
        self.layer_menu.add_command(label="Toggle Visibility", command=self._toggle_visibility)
        self.layer_menu.add_separator()
        self.layer_menu.add_command(label="Feather Mask", command=self._feather_mask)
        self.layer_menu.add_command(label="Invert Mask", command=self._invert_mask)
        # Bind right click on layer list
        self.layer_listbox.bind("<Button-3>", self._show_layer_context_menu)

        # Slider for transparency
        alpha_label = tk.Label(left_frame, text="Opacity", bg=label_bg, fg=label_fg, font=("Arial", 10, "bold"))
        alpha_label.pack(padx=5, pady=(10, 0))
        self.alpha_slider = tk.Scale(
            left_frame,
            from_=0,
            to=1,
            resolution=0.01,
            orient=tk.HORIZONTAL,
            command=self._on_alpha_change,
            bg=slider_bg,
            fg=slider_fg,
            highlightthickness=0,
        )
        self.alpha_slider.pack(padx=8, pady=4, fill=tk.X)
        self.alpha_slider.bind("<ButtonRelease-1>", lambda e: self._reset_history_flag())

        # Slider for brightness
        brightness_label = tk.Label(left_frame, text="Brightness", bg=label_bg, fg=label_fg, font=("Arial", 10, "bold"))
        brightness_label.pack(padx=5, pady=(10, 0))
        self.brightness_slider = tk.Scale(
            left_frame,
            from_=0.1,
            to=2,
            resolution=0.05,
            orient=tk.HORIZONTAL,
            command=self._on_brightness_change,
            bg=slider_bg,
            fg=slider_fg,
            highlightthickness=0,
        )
        self.brightness_slider.set(1.0)
        self.brightness_slider.pack(padx=8, pady=4, fill=tk.X)
        self.brightness_slider.bind("<ButtonRelease-1>", lambda e: self._reset_history_flag())

        # Slider for contrast
        contrast_label = tk.Label(left_frame, text="Contrast", bg=label_bg, fg=label_fg, font=("Arial", 10, "bold"))
        contrast_label.pack(padx=5, pady=(10, 0))
        self.contrast_slider = tk.Scale(
            left_frame,
            from_=0.1,
            to=2,
            resolution=0.05,
            orient=tk.HORIZONTAL,
            command=self._on_contrast_change,
            bg=slider_bg,
            fg=slider_fg,
            highlightthickness=0,
        )
        self.contrast_slider.set(1.0)
        self.contrast_slider.pack(padx=8, pady=4, fill=tk.X)
        self.contrast_slider.bind("<ButtonRelease-1>", lambda e: self._reset_history_flag())

        # Slider for colour (saturation)
        color_label = tk.Label(left_frame, text="Color", bg=label_bg, fg=label_fg, font=("Arial", 10, "bold"))
        color_label.pack(padx=5, pady=(10, 0))
        self.color_slider = tk.Scale(
            left_frame,
            from_=0.1,
            to=2,
            resolution=0.05,
            orient=tk.HORIZONTAL,
            command=self._on_color_change,
            bg=slider_bg,
            fg=slider_fg,
            highlightthickness=0,
        )
        self.color_slider.set(1.0)
        self.color_slider.pack(padx=8, pady=4, fill=tk.X)
        self.color_slider.bind("<ButtonRelease-1>", lambda e: self._reset_history_flag())

        # Slider for gamma (exposure)
        gamma_label = tk.Label(left_frame, text="Gamma", bg=label_bg, fg=label_fg, font=("Arial", 10, "bold"))
        gamma_label.pack(padx=5, pady=(10, 0))
        self.gamma_slider = tk.Scale(
            left_frame,
            from_=0.2,
            to=3.0,
            resolution=0.05,
            orient=tk.HORIZONTAL,
            command=self._on_gamma_change,
            bg=slider_bg,
            fg=slider_fg,
            highlightthickness=0,
        )
        self.gamma_slider.set(1.0)
        self.gamma_slider.pack(padx=8, pady=4, fill=tk.X)
        self.gamma_slider.bind("<ButtonRelease-1>", lambda e: self._reset_history_flag())

        # Buttons for tool selection
        tools_frame = tk.Frame(left_frame, bg=bg_toolbar)
        tools_frame.pack(padx=5, pady=(10, 5), fill=tk.X)
        # Create tool buttons and store them for highlighting
        self.tool_buttons = {}
        brush_btn = tk.Button(tools_frame, text="Brush", command=self._select_brush, bg=btn_bg, fg=btn_fg, relief=tk.RAISED, bd=1, font=("Arial", 9))
        brush_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        self.tool_buttons['brush'] = brush_btn
        eraser_btn = tk.Button(tools_frame, text="Eraser", command=self._select_eraser, bg=btn_bg, fg=btn_fg, relief=tk.RAISED, bd=1, font=("Arial", 9))
        eraser_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        self.tool_buttons['eraser'] = eraser_btn
        move_btn = tk.Button(tools_frame, text="Move", command=self._select_move, bg=btn_bg, fg=btn_fg, relief=tk.RAISED, bd=1, font=("Arial", 9))
        move_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        self.tool_buttons['move'] = move_btn
        mask_btn = tk.Button(tools_frame, text="Mask", command=self._select_mask, bg=btn_bg, fg=btn_fg, relief=tk.RAISED, bd=1, font=("Arial", 9))
        mask_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        self.tool_buttons['mask'] = mask_btn
        crop_btn = tk.Button(tools_frame, text="Crop", command=self._select_crop, bg=btn_bg, fg=btn_fg, relief=tk.RAISED, bd=1, font=("Arial", 9))
        crop_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        self.tool_buttons['crop'] = crop_btn
        select_btn = tk.Button(tools_frame, text="Select", command=self._select_select_tool, bg=btn_bg, fg=btn_fg, relief=tk.RAISED, bd=1, font=("Arial", 9))
        select_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        self.tool_buttons['select'] = select_btn
        text_btn = tk.Button(tools_frame, text="Text", command=self._select_text_tool, bg=btn_bg, fg=btn_fg, relief=tk.RAISED, bd=1, font=("Arial", 9))
        text_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        self.tool_buttons['text'] = text_btn
        # Button for applying filter to a region
        region_btn = tk.Button(tools_frame, text="Filter Region", command=self._select_filter_region, bg=btn_bg, fg=btn_fg, relief=tk.RAISED, bd=1, font=("Arial", 9))
        region_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        self.tool_buttons['filter_region'] = region_btn

        # Canvas for displaying composite image; use a neutral mid-grey to be easy on the eyes
        self.canvas = tk.Canvas(self, bg="#cdcdcd", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<ButtonPress-1>", self._on_canvas_press)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        # Status bar at bottom with soft colours
        status_frame = tk.Frame(self, bg="#e6e6e6")
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_label = tk.Label(status_frame, text="", bg="#e6e6e6", fg="#333333", anchor=tk.W)
        self.status_label.pack(fill=tk.X)
        # Update status on mouse motion
        self.canvas.bind("<Motion>", self._update_status)

        # Keyboard shortcuts for common operations (Photoshop‑like)
        # Undo/Redo
        self.bind_all("<Control-z>", lambda e: self._undo())
        self.bind_all("<Control-y>", lambda e: self._redo())
        # Duplicate layer (Ctrl+J)
        self.bind_all("<Control-j>", lambda e: self._duplicate_layer())
        # New layer (Ctrl+N)
        self.bind_all("<Control-n>", lambda e: self._new_layer())
        # Merge visible (Ctrl+E)
        self.bind_all("<Control-e>", lambda e: self._merge_visible_layers())
        # Save (Ctrl+S)
        self.bind_all("<Control-s>", lambda e: self._save_image())
        # Delete current layer (Delete key)
        self.bind_all("<Delete>", lambda e: self._delete_layer())

    def _create_menus(self):
        # File menu
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open Image...", command=self._open_image)
        file_menu.add_command(label="Save As...", command=self._save_image)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Undo", command=self._undo)
        edit_menu.add_command(label="Redo", command=self._redo)
        edit_menu.add_separator()
        edit_menu.add_command(label="Delete Layer", command=self._delete_layer)
        edit_menu.add_command(label="Duplicate Layer", command=self._duplicate_layer)
        edit_menu.add_separator()
        edit_menu.add_command(label="Move Layer Up", command=lambda: self._move_layer(-1))
        edit_menu.add_command(label="Move Layer Down", command=lambda: self._move_layer(1))
        edit_menu.add_separator()
        edit_menu.add_command(label="Merge Visible", command=self._merge_visible_layers)
        menubar.add_cascade(label="Edit", menu=edit_menu)

        # Filter menu
        filter_menu = tk.Menu(menubar, tearoff=0)
        filter_menu.add_command(label="Grayscale", command=lambda: self._preview_and_apply_filter("grayscale"))
        filter_menu.add_command(label="Invert", command=lambda: self._preview_and_apply_filter("invert"))
        filter_menu.add_command(label="Blur", command=lambda: self._preview_and_apply_filter("blur"))
        filter_menu.add_command(label="Sharpen", command=lambda: self._preview_and_apply_filter("sharpen"))
        filter_menu.add_separator()
        filter_menu.add_command(label="Emboss", command=lambda: self._preview_and_apply_filter("emboss"))
        filter_menu.add_command(label="Edge Enhance", command=lambda: self._preview_and_apply_filter("edge"))
        filter_menu.add_command(label="Contour", command=lambda: self._preview_and_apply_filter("contour"))
        filter_menu.add_command(label="Detail", command=lambda: self._preview_and_apply_filter("detail"))
        filter_menu.add_command(label="Smooth", command=lambda: self._preview_and_apply_filter("smooth"))
        filter_menu.add_command(label="Liquify (Swirl)", command=lambda: self._preview_and_apply_filter("liquify"))
        filter_menu.add_separator()
        filter_menu.add_command(label="Sepia", command=lambda: self._preview_and_apply_filter("sepia"))
        filter_menu.add_command(label="Skin Smooth", command=lambda: self._preview_and_apply_filter("skin smooth"))
        filter_menu.add_command(label="Auto Enhance", command=self._auto_enhance)
        filter_menu.add_command(label="Replace Background", command=self._replace_background)
        menubar.add_cascade(label="Filters", menu=filter_menu)

        # Transform menu
        transform_menu = tk.Menu(menubar, tearoff=0)
        transform_menu.add_command(label="Rotate 90° CW", command=lambda: self._rotate_layer(90))
        transform_menu.add_command(label="Rotate 180°", command=lambda: self._rotate_layer(180))
        transform_menu.add_command(label="Rotate 270° CW", command=lambda: self._rotate_layer(270))
        transform_menu.add_separator()
        transform_menu.add_command(label="Flip Horizontal", command=lambda: self._flip_layer("horizontal"))
        transform_menu.add_command(label="Flip Vertical", command=lambda: self._flip_layer("vertical"))
        transform_menu.add_separator()
        transform_menu.add_command(label="Resize Canvas (Scale Images)", command=self._resize_canvas)
        transform_menu.add_command(label="Resize Canvas (No Scaling)", command=self._resize_canvas_no_scale)
        menubar.add_cascade(label="Transform", menu=transform_menu)

        # Blend mode menu
        blend_menu = tk.Menu(menubar, tearoff=0)
        blend_menu.add_command(label="Normal", command=lambda: self._set_blend_mode('normal'))
        blend_menu.add_command(label="Multiply", command=lambda: self._set_blend_mode('multiply'))
        blend_menu.add_command(label="Screen", command=lambda: self._set_blend_mode('screen'))
        blend_menu.add_command(label="Overlay", command=lambda: self._set_blend_mode('overlay'))
        blend_menu.add_command(label="Soft Light", command=lambda: self._set_blend_mode('softlight'))
        menubar.add_cascade(label="Blend Mode", menu=blend_menu)

        # View menu to toggle layer visibility
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Toggle Layer Visibility", command=self._toggle_visibility)
        menubar.add_cascade(label="View", menu=view_menu)

        self.config(menu=menubar)

        # Export menu for common social media presets
        export_menu = tk.Menu(menubar, tearoff=0)
        export_menu.add_command(label="Instagram (1080×1080)", command=lambda: self._export_preset(1080, 1080))
        export_menu.add_command(label="Twitter 16:9 (1920×1080)", command=lambda: self._export_preset(1920, 1080))
        export_menu.add_command(label="Facebook Cover (820×312)", command=lambda: self._export_preset(820, 312))
        menubar.add_cascade(label="Export", menu=export_menu)

        # Collage menu for creating collages and auto layout
        collage_menu = tk.Menu(menubar, tearoff=0)
        collage_menu.add_command(label="Create Collage from Files", command=self._create_collage_from_files)
        collage_menu.add_command(label="Layout Visible Layers as Collage", command=self._layout_visible_layers)
        # New advanced collage creation command
        collage_menu.add_command(label="Create Collage (Advanced)", command=self._create_collage_advanced)
        # Auto balance layers for cohesive composition
        collage_menu.add_command(label="Auto Balance Layers", command=self._auto_balance_layers)
        menubar.add_cascade(label="Collage", menu=collage_menu)

        # Templates menu for quick layouts
        templates_menu = tk.Menu(menubar, tearoff=0)
        templates_menu.add_command(label="2×2 Grid", command=lambda: self._create_template_layout("2x2"))
        templates_menu.add_command(label="3×3 Grid", command=lambda: self._create_template_layout("3x3"))
        templates_menu.add_command(label="1×3 Horizontal", command=lambda: self._create_template_layout("1x3h"))
        templates_menu.add_command(label="3×1 Vertical", command=lambda: self._create_template_layout("3x1v"))
        templates_menu.add_command(label="Random Mosaic", command=lambda: self._create_template_layout("random"))
        menubar.add_cascade(label="Templates", menu=templates_menu)

        # Drafts menu for saving/loading temporary projects
        drafts_menu = tk.Menu(menubar, tearoff=0)
        drafts_menu.add_command(label="Save Draft", command=self._save_draft)
        drafts_menu.add_command(label="Load Draft", command=self._load_draft)
        drafts_menu.add_command(label="Delete All Drafts", command=self._delete_all_drafts)
        menubar.add_cascade(label="Drafts", menu=drafts_menu)

    # ------------------------------------------------------------------
    # Layer management
    # ------------------------------------------------------------------
    def _new_blank_layer(self):
        """Deprecated wrapper for backwards compatibility. Calls _new_layer()."""
        self._new_layer()

    def _new_layer(self):
        """Create a new layer of various types based on user selection.

        Options include a blank transparent layer, a solid colour fill,
        a gradient fill or a simple pattern.  The new layer uses the size
        of the first existing layer as its canvas.  If no layers exist
        yet, the user is prompted to open an image first.
        """
        # Determine canvas/base size.  If no layers exist yet, prompt user
        # for initial canvas dimensions and (optionally) background colour.
        if not self.layers:
            # Ask width and height for new document
            width = simpledialog.askinteger(
                "Canvas Width",
                "Enter new canvas width (pixels):",
                initialvalue=800,
                minvalue=1,
            )
            if width is None:
                return
            height = simpledialog.askinteger(
                "Canvas Height",
                "Enter new canvas height (pixels):",
                initialvalue=600,
                minvalue=1,
            )
            if height is None:
                return
            base_size = (width, height)
            # Ask whether to fill the base with a colour
            fill_choice = messagebox.askyesno("Background", "Fill background with colour?")
            if fill_choice:
                colour = colorchooser.askcolor(title="Choose background colour")
                rgb = None
                if colour and colour[0]:
                    rgb = tuple(int(c) for c in colour[0])
                # If no colour chosen, default to white
                if rgb is None:
                    rgb = (255, 255, 255)
                base_img = Image.new("RGBA", base_size, rgb + (255,))
            else:
                base_img = Image.new("RGBA", base_size, (0, 0, 0, 0))
            # Create base layer
            base_layer_name = simpledialog.askstring("Layer Name", "Enter name for first layer:", initialvalue="Background")
            if not base_layer_name:
                base_layer_name = "Background"
            base_layer = Layer(base_img, base_layer_name)
            # Save history and add
            self._save_history()
            self.layers.append(base_layer)
            self.current_layer_index = 0
            # Set canvas size accordingly
            self.canvas.config(width=width, height=height)
            self._refresh_layer_list()
            self._update_composite()
            # If user only wanted a single base layer, exit now
            # Additional layers can be created by calling New Layer again.
            return
        else:
            base_size = self.layers[0].image.size
        # Ask for type of layer with expanded options
        layer_type = simpledialog.askstring(
            "New Layer",
            "Layer type (blank, color, gradient, pattern, noise, circle, ring):",
            initialvalue="blank",
        )
        if not layer_type:
            return
        layer_type = layer_type.strip().lower()
        new_img = None
        layer_name = simpledialog.askstring("Layer Name", "Enter layer name:", initialvalue=f"Layer {len(self.layers)}")
        if not layer_name:
            layer_name = f"Layer {len(self.layers)}"
        if layer_type == "blank":
            new_img = Image.new("RGBA", base_size, (0, 0, 0, 0))
        elif layer_type in ("color", "solid", "colour"):
            # Ask colour
            colour = colorchooser.askcolor(title="Choose fill colour")
            if not colour or not colour[0]:
                return
            rgb = tuple(int(c) for c in colour[0])
            new_img = Image.new("RGBA", base_size, rgb + (255,))
        elif layer_type == "gradient":
            # Ask orientation and colours
            orientation = simpledialog.askstring(
                "Gradient Orientation", "Enter orientation (horizontal or vertical):", initialvalue="horizontal"
            )
            if not orientation:
                return
            orientation = orientation.strip().lower()
            c1 = colorchooser.askcolor(title="Gradient start colour")
            if not c1 or not c1[0]:
                return
            c2 = colorchooser.askcolor(title="Gradient end colour")
            if not c2 or not c2[0]:
                return
            r1, g1, b1 = [int(v) for v in c1[0]]
            r2, g2, b2 = [int(v) for v in c2[0]]
            new_img = Image.new("RGBA", base_size)
            w, h = base_size
            if orientation.startswith("h"):
                # horizontal gradient left to right
                for x in range(w):
                    t = x / (w - 1) if w > 1 else 0
                    r = int(r1 + (r2 - r1) * t)
                    g = int(g1 + (g2 - g1) * t)
                    b = int(b1 + (b2 - b1) * t)
                    for y in range(h):
                        new_img.putpixel((x, y), (r, g, b, 255))
            else:
                # vertical gradient top to bottom
                for y in range(h):
                    t = y / (h - 1) if h > 1 else 0
                    r = int(r1 + (r2 - r1) * t)
                    g = int(g1 + (g2 - g1) * t)
                    b = int(b1 + (b2 - b1) * t)
                    for x in range(w):
                        new_img.putpixel((x, y), (r, g, b, 255))
        elif layer_type == "pattern":
            # Create a simple striped or checker pattern
            ptype = simpledialog.askstring(
                "Pattern Type", "Enter pattern (stripes or checker):", initialvalue="stripes"
            )
            if ptype is None:
                return
            ptype = ptype.strip().lower()
            stripe_width = simpledialog.askinteger(
                "Pattern Size",
                "Enter pattern size in pixels (default 20)",
                initialvalue=20,
                minvalue=1,
                maxvalue=200,
            )
            if not stripe_width:
                stripe_width = 20
            c = colorchooser.askcolor(title="Pattern colour")
            if not c or not c[0]:
                return
            pattern_color = tuple(int(v) for v in c[0])
            new_img = Image.new("RGBA", base_size, (0, 0, 0, 0))
            w, h = base_size
            for y in range(h):
                for x in range(w):
                    if ptype.startswith("str"):
                        band = ((x // stripe_width) % 2)
                    else:
                        band = (((x // stripe_width) + (y // stripe_width)) % 2)
                    if band == 0:
                        new_img.putpixel((x, y), pattern_color + (255,))
        elif layer_type == "noise":
            # Create random noise across the layer; ask for density (0-100)
            density = simpledialog.askinteger(
                "Noise Density", "Enter noise density percentage (0-100)", initialvalue=50, minvalue=0, maxvalue=100
            )
            if density is None:
                density = 50
            # Ask for foreground colour of noise
            fg_colour = colorchooser.askcolor(title="Noise colour (foreground)", initialcolor="#ffffff")
            if not fg_colour or not fg_colour[0]:
                return
            fr, fg, fb = [int(v) for v in fg_colour[0]]
            # Ask for background colour (for non-noise pixels)
            bg_colour = colorchooser.askcolor(title="Background colour (behind noise)", initialcolor="#000000")
            if not bg_colour or not bg_colour[0]:
                return
            br, bg_, bb = [int(v) for v in bg_colour[0]]
            new_img = Image.new("RGBA", base_size, (br, bg_, bb, 255))
            w, h = base_size
            import random
            for y in range(h):
                for x in range(w):
                    if random.randint(0, 100) < density:
                        new_img.putpixel((x, y), (fr, fg, fb, 255))
        elif layer_type == "circle":
            # Ask circle radius fraction and colour
            radius_ratio = simpledialog.askfloat(
                "Circle Size",
                "Enter circle radius as fraction of canvas (0-1)",
                initialvalue=0.3,
                minvalue=0.01,
                maxvalue=1.0,
            )
            if radius_ratio is None:
                return
            ccol = colorchooser.askcolor(title="Circle colour")
            if not ccol or not ccol[0]:
                return
            rc, gc, bc = [int(v) for v in ccol[0]]
            new_img = Image.new("RGBA", base_size, (0, 0, 0, 0))
            w, h = base_size
            # Determine radius
            rad = int(min(w, h) * radius_ratio)
            cx = w // 2
            cy = h // 2
            for y in range(h):
                for x in range(w):
                    if (x - cx) ** 2 + (y - cy) ** 2 <= rad ** 2:
                        new_img.putpixel((x, y), (rc, gc, bc, 255))
        elif layer_type == "ring":
            # Ask inner and outer radius fractions and colour
            outer_ratio = simpledialog.askfloat(
                "Outer Radius",
                "Enter outer radius fraction (0-1)",
                initialvalue=0.45,
                minvalue=0.01,
                maxvalue=1.0,
            )
            if outer_ratio is None:
                return
            inner_ratio = simpledialog.askfloat(
                "Inner Radius",
                "Enter inner radius fraction (0-1, less than outer)",
                initialvalue=0.3,
                minvalue=0.0,
                maxvalue=outer_ratio,
            )
            if inner_ratio is None:
                inner_ratio = 0.0
            ring_colour = colorchooser.askcolor(title="Ring colour")
            if not ring_colour or not ring_colour[0]:
                return
            rr, rg, rb = [int(v) for v in ring_colour[0]]
            new_img = Image.new("RGBA", base_size, (0, 0, 0, 0))
            w, h = base_size
            max_rad = int(min(w, h) * outer_ratio)
            min_rad = int(min(w, h) * inner_ratio)
            cx = w // 2
            cy = h // 2
            for y in range(h):
                for x in range(w):
                    dist2 = (x - cx) ** 2 + (y - cy) ** 2
                    if min_rad ** 2 < dist2 <= max_rad ** 2:
                        new_img.putpixel((x, y), (rr, rg, rb, 255))
        else:
            # Unknown type: create blank
            new_img = Image.new("RGBA", base_size, (0, 0, 0, 0))
        # Create and add layer
        layer = Layer(new_img, layer_name)
        self._save_history()
        self.layers.append(layer)
        self.current_layer_index = len(self.layers) - 1
        self._refresh_layer_list()
        self._update_composite()

    def _open_image(self):
        """Load an image from disk and create a new layer with it.

        The selected file will be opened using Pillow.  If this is the
        first layer being added, the canvas size will be set to the
        image's dimensions.  Additional images can be loaded as
        separate layers on top.
        """
        filetypes = [("Image files", "*.png;*.jpg;*.jpeg;*.bmp;*.gif"), ("All files", "*.*")]
        filepath = filedialog.askopenfilename(title="Open Image", filetypes=filetypes)
        if not filepath:
            return
        try:
            image = Image.open(filepath)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open image: {e}")
            return
        # Convert to RGBA to support transparency
        image = image.convert("RGBA")
        layer_name = os.path.basename(filepath)
        layer = Layer(image, layer_name)
        self._save_history()
        self.layers.append(layer)
        self.current_layer_index = len(self.layers) - 1
        # If this is the first layer, set canvas size
        if len(self.layers) == 1:
            self.canvas.config(width=image.width, height=image.height)
        self._refresh_layer_list()
        self._update_composite()

    def _save_image(self):
        """Save the current composite image to disk."""
        if not self.layers:
            messagebox.showinfo("Nothing to save", "There is no image to save.")
            return
        filetypes = [("PNG", "*.png"), ("JPEG", "*.jpg"), ("All files", "*.*")]
        filepath = filedialog.asksaveasfilename(title="Save Image", defaultextension=".png", filetypes=filetypes)
        if not filepath:
            return
        composite = self._create_composite_image()
        try:
            composite.save(filepath)
            messagebox.showinfo("Saved", f"Image saved to {filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save image: {e}")

    def _delete_layer(self):
        """Delete the currently selected layer."""
        if self.current_layer_index is None:
            return
        self._save_history()
        del self.layers[self.current_layer_index]
        # Adjust selected index
        if not self.layers:
            self.current_layer_index = None
            self.canvas.delete("all")
        else:
            self.current_layer_index = max(0, self.current_layer_index - 1)
        self._refresh_layer_list()
        self._update_composite()

    def _merge_visible_layers(self):
        """Merge all visible layers into a single layer.

        Hidden layers are left untouched.  This is useful to flatten
        completed portions of your composition so that you can continue
        editing with a simpler layer stack.
        """
        if not self.layers:
            return
        # Create composite of visible layers
        composite = self._create_composite_image(include_hidden=False)
        # Remove all visible layers and insert merged one
        new_layers = []
        for layer in self.layers:
            if not layer.visible:
                new_layers.append(layer)
        self._save_history()
        merged_layer = Layer(composite, "Merged")
        new_layers.append(merged_layer)
        self.layers = new_layers
        self.current_layer_index = len(self.layers) - 1
        self._refresh_layer_list()
        self._update_composite()

    def _toggle_visibility(self):
        """Toggle the visibility of the currently selected layer."""
        if self.current_layer_index is None:
            return
        layer = self.layers[self.current_layer_index]
        self._save_history()
        layer.visible = not layer.visible
        self._refresh_layer_list()
        self._update_composite()

    def _refresh_layer_list(self):
        """Update the layer list UI to reflect current layers."""
        self.layer_listbox.delete(0, tk.END)
        for idx, layer in enumerate(self.layers):
            visibility = "👁️ " if layer.visible else "🚫 "
            name = visibility + layer.name
            self.layer_listbox.insert(tk.END, name)
        if self.current_layer_index is not None:
            self.layer_listbox.select_set(self.current_layer_index)
        self.layer_listbox.update_idletasks()

    def _on_layer_select(self, event):
        """Callback when a different layer is selected in the listbox."""
        selection = self.layer_listbox.curselection()
        if selection:
            self.current_layer_index = selection[0]
            layer = self.layers[self.current_layer_index]
            # Update sliders to reflect selected layer's properties
            self.alpha_slider.set(layer.alpha)
            self.brightness_slider.set(layer.brightness)
            if hasattr(self, 'contrast_slider'):
                self.contrast_slider.set(layer.contrast)
            if hasattr(self, 'color_slider'):
                self.color_slider.set(layer.color)
            # Update gamma slider if present
            if hasattr(self, 'gamma_slider'):
                try:
                    self.gamma_slider.set(layer.gamma)
                except Exception:
                    pass

    def _rename_layer(self, event) -> None:
        """Prompt the user to rename the double‑clicked layer."""
        index = self.layer_listbox.nearest(event.y)
        if index < 0 or index >= len(self.layers):
            return
        self.current_layer_index = index
        current_name = self.layers[index].name
        new_name = simpledialog.askstring("Rename Layer", "Enter new layer name:", initialvalue=current_name)
        if new_name and new_name.strip():
            self._save_history()
            self.layers[index].name = new_name.strip()
            self._refresh_layer_list()
    # ------------------------------------------------------------------
    # Composite management
    # ------------------------------------------------------------------
    def _create_composite_image(self, include_hidden: bool = True) -> Image.Image:
        """Return a new PIL image that composites all layers.

        :param include_hidden: if False, skip layers whose ``visible``
            attribute is False.
        :returns: an ``Image`` object representing the composite.
        """
        if not self.layers:
            return None
        # Start from a blank transparent canvas matching the first layer
        base_size = self.layers[0].image.size
        composite = Image.new("RGBA", base_size, (0, 0, 0, 0))
        # Build composite by blending layers according to their blend_mode
        for layer in self.layers:
            if include_hidden or layer.visible:
                ox, oy = layer.offset
                # Create an overlay image the size of the composite with layer placed at its offset
                overlay = Image.new("RGBA", base_size, (0, 0, 0, 0))
                overlay.paste(layer.image, (int(ox), int(oy)), layer.image)
                if layer.blend_mode == 'normal':
                    composite = Image.alpha_composite(composite, overlay)
                elif layer.blend_mode in ('multiply', 'screen', 'overlay', 'softlight'):
                    # Custom blend modes with alpha compositing.  Split images into channels.
                    b_r, b_g, b_b, b_a = composite.split()
                    o_r, o_g, o_b, o_a = overlay.split()
                    # Compute inverted overlay alpha once
                    inv_o_a = ImageChops.invert(o_a)
                    # Compute new alpha: o_a + b_a * (1 - o_a/255)
                    new_a = ImageChops.add(o_a, ImageChops.multiply(b_a, inv_o_a))
                    # Determine blended colour channels based on blend mode
                    if layer.blend_mode == 'multiply':
                        # Multiply colour channels
                        blend_r = ImageChops.multiply(b_r, o_r)
                        blend_g = ImageChops.multiply(b_g, o_g)
                        blend_b = ImageChops.multiply(b_b, o_b)
                    elif layer.blend_mode == 'screen':
                        # Screen: 255 - (255 - base)*(255 - overlay)/255
                        blend_r = ImageChops.screen(b_r, o_r)
                        blend_g = ImageChops.screen(b_g, o_g)
                        blend_b = ImageChops.screen(b_b, o_b)
                    elif layer.blend_mode == 'overlay':
                        # Overlay: if base < 128 then multiply, else screen the inverted values
                        try:
                            blend_r = ImageChops.overlay(b_r, o_r)
                            blend_g = ImageChops.overlay(b_g, o_g)
                            blend_b = ImageChops.overlay(b_b, o_b)
                        except Exception:
                            # Fallback: approximate overlay by combining multiply and screen
                            blend_r = ImageChops.add(ImageChops.multiply(b_r, o_r), ImageChops.screen(b_r, o_r))
                            blend_g = ImageChops.add(ImageChops.multiply(b_g, o_g), ImageChops.screen(b_g, o_g))
                            blend_b = ImageChops.add(ImageChops.multiply(b_b, o_b), ImageChops.screen(b_b, o_b))
                    elif layer.blend_mode == 'softlight':
                        # Soft light blending: uses PIL's built‑in soft_light if available
                        try:
                            blend_r = ImageChops.soft_light(b_r, o_r)
                            blend_g = ImageChops.soft_light(b_g, o_g)
                            blend_b = ImageChops.soft_light(b_b, o_b)
                        except Exception:
                            # Fallback: use overlay
                            blend_r = ImageChops.overlay(b_r, o_r)
                            blend_g = ImageChops.overlay(b_g, o_g)
                            blend_b = ImageChops.overlay(b_b, o_b)
                    else:
                        # Should not reach here, fallback to normal
                        composite = Image.alpha_composite(composite, overlay)
                        continue
                    # Combine base and blended colours according to alpha
                    out_r = ImageChops.add(ImageChops.multiply(b_r, inv_o_a), ImageChops.multiply(blend_r, o_a))
                    out_g = ImageChops.add(ImageChops.multiply(b_g, inv_o_a), ImageChops.multiply(blend_g, o_a))
                    out_b = ImageChops.add(ImageChops.multiply(b_b, inv_o_a), ImageChops.multiply(blend_b, o_a))
                    composite = Image.merge("RGBA", (out_r, out_g, out_b, new_a))
                else:
                    # Fallback to normal blending
                    composite = Image.alpha_composite(composite, overlay)
        return composite

    def _update_composite(self):
        """Redraw the main canvas with the current composite image."""
        if not self.layers:
            self.canvas.delete("all")
            return
        composite = self._create_composite_image()
        # Convert to PhotoImage for Tkinter display
        self.tk_composite = ImageTk.PhotoImage(composite)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_composite)

    def _show_layer_context_menu(self, event):
        """Show context menu for layers on right click."""
        # Select the clicked item
        try:
            index = self.layer_listbox.nearest(event.y)
            self.layer_listbox.select_clear(0, tk.END)
            self.layer_listbox.select_set(index)
            self.current_layer_index = index
        except Exception:
            return
        self.layer_menu.tk_popup(event.x_root, event.y_root)

    def _update_status(self, event):
        """Update the status bar with current tool and mouse coordinates."""
        tool = self.current_tool if self.current_tool else "None"
        x, y = event.x, event.y
        self.status_label.config(text=f"Tool: {tool}    Position: ({x}, {y})")

    def _highlight_tool(self) -> None:
        """Update the appearance of tool buttons to indicate the active tool."""
        for name, btn in getattr(self, 'tool_buttons', {}).items():
            if self.current_tool == name:
                # Highlight active tool with a slightly darker shade and sunken relief
                # Slightly darker highlight when active
                btn.config(relief=tk.SUNKEN, bg="#d0d0d0")
            else:
                # Reset to normal appearance
                btn.config(relief=tk.RAISED, bg="#e6e6e6")

    def _set_blend_mode(self, mode: str) -> None:
        """Set the blending mode of the currently selected layer and update the composite."""
        if self.current_layer_index is None:
            return
        if mode not in ('normal', 'multiply', 'screen', 'overlay', 'softlight'):
            messagebox.showinfo("Unsupported blend mode", f"Blend mode '{mode}' is not supported.")
            return
        self._save_history()
        self.layers[self.current_layer_index].blend_mode = mode
        self._update_composite()
    # ------------------------------------------------------------------
    # History operations
    # ------------------------------------------------------------------
    def _save_history(self):
        """Save a snapshot of the current editor state for undo/redo."""
        # Discard any redo states beyond the current index
        if self.history_index < len(self.history) - 1:
            self.history = self.history[: self.history_index + 1]
        # Create snapshot of layers
        snapshot_layers = []
        for layer in self.layers:
            # Copy original image to preserve pixel data
            layer_data = {
                "image": layer.original.copy(),
                "mask": layer.mask.copy(),
                "offset": layer.offset,
                "name": layer.name,
                "visible": layer.visible,
                "alpha": layer.alpha,
                "brightness": layer.brightness,
                "contrast": layer.contrast,
                "color": layer.color,
                "gamma": layer.gamma,
                "blend_mode": layer.blend_mode,
                "red": layer.red,
                "green": layer.green,
                "blue": layer.blue,
            }
            snapshot_layers.append(layer_data)
        snapshot = {
            "layers": snapshot_layers,
            "current_index": self.current_layer_index,
        }
        self.history.append(snapshot)
        # Enforce history size limit
        if len(self.history) > self.max_history:
            # remove oldest state and adjust index accordingly
            self.history.pop(0)
            if self.history_index > 0:
                self.history_index -= 1
        # Move history index to the end
        self.history_index = len(self.history) - 1

    def _restore_history_state(self, snapshot: dict) -> None:
        """Restore layers and selection from a snapshot."""
        self.layers = []
        for item in snapshot["layers"]:
            layer = Layer(item["image"], item["name"])
            # Restore mask and offset
            if "mask" in item:
                layer.mask = item["mask"].copy()
            if "offset" in item:
                layer.offset = item["offset"]
            layer.visible = item["visible"]
            layer.alpha = item["alpha"]
            layer.brightness = item["brightness"]
            layer.contrast = item["contrast"]
            layer.color = item["color"]
            # Restore gamma and blend_mode if present
            if "gamma" in item:
                layer.gamma = item["gamma"]
            if "blend_mode" in item:
                layer.blend_mode = item["blend_mode"]
            # Restore selective colour adjustments
            if "red" in item:
                layer.red = item["red"]
            if "green" in item:
                layer.green = item["green"]
            if "blue" in item:
                layer.blue = item["blue"]
            layer.apply_adjustments()
            self.layers.append(layer)
        self.current_layer_index = snapshot.get("current_index")
        self._refresh_layer_list()
        self._update_composite()

    def _undo(self):
        """Revert to the previous state in history."""
        if self.history_index <= 0:
            return
        self.history_index -= 1
        snapshot = self.history[self.history_index]
        self._restore_history_state(snapshot)

    def _redo(self):
        """Advance to the next state in history if available."""
        if self.history_index >= len(self.history) - 1:
            return
        self.history_index += 1
        snapshot = self.history[self.history_index]
        self._restore_history_state(snapshot)

    # ------------------------------------------------------------------
    # Layer operations
    # ------------------------------------------------------------------
    def _duplicate_layer(self):
        """Create a duplicate of the currently selected layer."""
        if self.current_layer_index is None:
            return
        self._save_history()
        src = self.layers[self.current_layer_index]
        new_img = src.original.copy()
        name = src.name + " copy"
        dup_layer = Layer(new_img, name)
        dup_layer.visible = src.visible
        dup_layer.alpha = src.alpha
        dup_layer.brightness = src.brightness
        dup_layer.contrast = src.contrast
        dup_layer.color = src.color
        # Copy mask and offset
        dup_layer.mask = src.mask.copy()
        dup_layer.offset = src.offset
        dup_layer.apply_adjustments()
        # Insert above the original layer
        self.layers.insert(self.current_layer_index + 1, dup_layer)
        self.current_layer_index += 1
        self._refresh_layer_list()
        self._update_composite()

    def _move_layer(self, offset: int) -> None:
        """Move the selected layer up or down by one position.

        :param offset: -1 to move up, +1 to move down.
        """
        if self.current_layer_index is None:
            return
        new_index = self.current_layer_index + offset
        if new_index < 0 or new_index >= len(self.layers):
            return
        self._save_history()
        # Swap layers
        self.layers[self.current_layer_index], self.layers[new_index] = self.layers[new_index], self.layers[self.current_layer_index]
        self.current_layer_index = new_index
        self._refresh_layer_list()
        self._update_composite()

    # ------------------------------------------------------------------
    # Transform operations
    # ------------------------------------------------------------------
    def _rotate_layer(self, degrees: int) -> None:
        """Rotate the currently selected layer clockwise by the given degrees."""
        if self.current_layer_index is None:
            return
        self._save_history()
        layer = self.layers[self.current_layer_index]
        # rotate original image around centre, expand to fit
        # Pillow rotates counter-clockwise by default; we pass 360 - degrees for clockwise
        rotated = layer.original.rotate(-degrees, expand=True)
        # Resize rotated image to canvas size by pasting onto transparent canvas
        base_size = self.layers[0].image.size
        new_img = Image.new("RGBA", base_size, (0, 0, 0, 0))
        # centre rotated image on base
        x = (base_size[0] - rotated.width) // 2
        y = (base_size[1] - rotated.height) // 2
        new_img.paste(rotated, (x, y), rotated)
        layer.original = new_img
        layer.apply_adjustments()
        self._update_composite()

    def _flip_layer(self, axis: str) -> None:
        """Flip the currently selected layer horizontally or vertically."""
        if self.current_layer_index is None:
            return
        self._save_history()
        layer = self.layers[self.current_layer_index]
        if axis == "horizontal":
            flipped = layer.original.transpose(Image.FLIP_LEFT_RIGHT)
        elif axis == "vertical":
            flipped = layer.original.transpose(Image.FLIP_TOP_BOTTOM)
        else:
            return
        # Paste onto same sized canvas to maintain alignment
        base_size = layer.original.size
        new_img = Image.new("RGBA", base_size, (0, 0, 0, 0))
        new_img.paste(flipped, (0, 0), flipped)
        layer.original = new_img
        layer.apply_adjustments()
        self._update_composite()

    def _resize_canvas(self) -> None:
        """Prompt user for new dimensions and resize all layers accordingly."""
        if not self.layers:
            return
        # Ask for new width and height
        current_w = self.layers[0].image.width
        current_h = self.layers[0].image.height
        # Use simpledialog to ask for width and height
        new_w = simpledialog.askinteger("Resize", "Enter new width", initialvalue=current_w, minvalue=1)
        if new_w is None:
            return
        new_h = simpledialog.askinteger("Resize", "Enter new height", initialvalue=current_h, minvalue=1)
        if new_h is None:
            return
        # Save history before resizing
        self._save_history()
        scale_x = new_w / current_w
        scale_y = new_h / current_h
        for layer in self.layers:
            # Resize original image
            w, h = layer.original.size
            resized = layer.original.resize((int(w * scale_x), int(h * scale_y)), resample=Image.BICUBIC)
            layer.original = resized
            # Resize mask accordingly
            layer.mask = layer.mask.resize((int(w * scale_x), int(h * scale_y)), resample=Image.BICUBIC)
            # Scale offset
            ox, oy = layer.offset
            layer.offset = (ox * scale_x, oy * scale_y)
            # Update adjustments
            layer.apply_adjustments()
        # Update canvas size
        self.canvas.config(width=new_w, height=new_h)
        self._refresh_layer_list()
        self._update_composite()

    def _resize_canvas_no_scale(self) -> None:
        """Change the canvas size without scaling the existing layers.

        This operation behaves similarly to the canvas size command in
        professional editors: the dimensions of the drawing surface
        change, but each layer's pixel data remains unscaled.  When
        enlarging, empty space is added around the existing content.  If
        the new size is smaller than the current canvas, the image is
        cropped at the top‑left corner.  All layer offsets are preserved.
        """
        if not self.layers:
            return
        # Current canvas dimensions are taken from the first layer
        current_w = self.layers[0].image.width
        current_h = self.layers[0].image.height
        # Ask for new width and height
        new_w = simpledialog.askinteger(
            "Resize Canvas (No Scaling)",
            "Enter new width",
            initialvalue=current_w,
            minvalue=1,
        )
        if new_w is None:
            return
        new_h = simpledialog.askinteger(
            "Resize Canvas (No Scaling)",
            "Enter new height",
            initialvalue=current_h,
            minvalue=1,
        )
        if new_h is None:
            return
        # If dimensions are unchanged, nothing to do
        if new_w == current_w and new_h == current_h:
            return
        # Save history before making changes
        self._save_history()
        # Enlarge canvas: if new dimensions are greater than current
        if new_w >= current_w and new_h >= current_h:
            for layer in self.layers:
                # Create new transparent canvas for original image
                new_img = Image.new("RGBA", (new_w, new_h), (0, 0, 0, 0))
                # Paste existing original at its offset; offset is relative to
                # the top‑left, so paste at (0,0) and later offset will shift
                new_img.paste(layer.original, (0, 0), layer.original)
                layer.original = new_img
                # Expand mask similarly; fill new areas with 0 (fully hidden) so
                # transparency is preserved
                new_mask = Image.new("L", (new_w, new_h), 0)
                new_mask.paste(layer.mask, (0, 0))
                layer.mask = new_mask
                # Offsets remain unchanged because we paste at (0,0)
                layer.apply_adjustments()
            # Update canvas size
            self.canvas.config(width=new_w, height=new_h)
            self._refresh_layer_list()
            self._update_composite()
            return
        # Otherwise, we are shrinking the canvas; crop at top‑left (0,0)
        # Use _perform_crop helper to crop all layers and update offsets
        # Compose bounding coordinates from (0,0) to (new_w, new_h)
        # We call _perform_crop directly using canvas coordinates
        self._perform_crop(0, 0, new_w, new_h)
        # After _perform_crop, canvas size will be updated

    def _reset_history_flag(self):
        """Reset the history saved flag after a slider or drawing operation."""
        self._history_saved_for_stroke = False

    # ------------------------------------------------------------------
    # Mask refinement operations
    # ------------------------------------------------------------------
    def _feather_mask(self) -> None:
        """Blur the mask edges of the currently selected layer to soften transitions.

        Prompts the user for a blur radius and applies a Gaussian blur
        to the layer's mask.  A larger radius results in a softer edge.
        """
        if self.current_layer_index is None:
            return
        radius = simpledialog.askinteger("Feather Mask", "Enter blur radius (1-50)", initialvalue=5, minvalue=1, maxvalue=50)
        if radius is None:
            return
        self._save_history()
        layer = self.layers[self.current_layer_index]
        # Apply Gaussian blur to the mask
        layer.mask = layer.mask.filter(ImageFilter.GaussianBlur(radius=radius))
        layer.apply_adjustments()
        self._update_composite()

    def _invert_mask(self) -> None:
        """Invert the mask of the currently selected layer.

        Pixels that were hidden become visible and vice versa.  Useful
        when refining selection areas or quickly toggling the mask.
        """
        if self.current_layer_index is None:
            return
        self._save_history()
        layer = self.layers[self.current_layer_index]
        layer.mask = ImageChops.invert(layer.mask)
        layer.apply_adjustments()
        self._update_composite()

    # ------------------------------------------------------------------
    # Adjustments and filters
    # ------------------------------------------------------------------
    def _on_alpha_change(self, value):
        if self.current_layer_index is None:
            return
        layer = self.layers[self.current_layer_index]
        # Save history only on first adjustment within a slider movement
        if not self._history_saved_for_stroke:
            self._save_history()
            self._history_saved_for_stroke = True
        layer.alpha = float(value)
        layer.apply_adjustments()
        self._update_composite()

    def _on_brightness_change(self, value):
        if self.current_layer_index is None:
            return
        layer = self.layers[self.current_layer_index]
        if not self._history_saved_for_stroke:
            self._save_history()
            self._history_saved_for_stroke = True
        layer.brightness = float(value)
        layer.apply_adjustments()
        self._update_composite()

    def _on_contrast_change(self, value):
        """Callback when the contrast slider is moved."""
        if self.current_layer_index is None:
            return
        layer = self.layers[self.current_layer_index]
        if not self._history_saved_for_stroke:
            self._save_history()
            self._history_saved_for_stroke = True
        layer.contrast = float(value)
        layer.apply_adjustments()
        self._update_composite()

    def _on_color_change(self, value):
        """Callback when the colour (saturation) slider is moved."""
        if self.current_layer_index is None:
            return
        layer = self.layers[self.current_layer_index]
        if not self._history_saved_for_stroke:
            self._save_history()
            self._history_saved_for_stroke = True
        layer.color = float(value)
        layer.apply_adjustments()
        self._update_composite()

    def _on_gamma_change(self, value):
        """Callback when the gamma (exposure) slider is moved."""
        if self.current_layer_index is None:
            return
        layer = self.layers[self.current_layer_index]
        if not self._history_saved_for_stroke:
            self._save_history()
            self._history_saved_for_stroke = True
        layer.gamma = float(value)
        layer.apply_adjustments()
        self._update_composite()

    def _apply_filter(self, filter_name: str):
        if self.current_layer_index is None:
            return
        try:
            # Save state before applying filter
            self._save_history()
            layer = self.layers[self.current_layer_index]
            layer.apply_filter(filter_name)
            self._update_composite()
        except ValueError as e:
            messagebox.showerror("Filter error", str(e))

    def _auto_enhance(self) -> None:
        """Automatically adjust exposure, contrast and colour, then apply mild sharpening.

        This simple implementation enhances the current layer by boosting
        brightness, contrast and saturation slightly and applying an
        unsharp mask to improve clarity.  It saves the operation to
        history so it can be undone.
        """
        if self.current_layer_index is None:
            return
        self._save_history()
        layer = self.layers[self.current_layer_index]
        img = layer.original
        # Boost brightness, contrast and colour
        enh = ImageEnhance.Brightness(img)
        img = enh.enhance(1.1)
        enh = ImageEnhance.Contrast(img)
        img = enh.enhance(1.15)
        enh = ImageEnhance.Color(img)
        img = enh.enhance(1.1)
        # Apply mild sharpen
        img = img.filter(ImageFilter.UnsharpMask(radius=1, percent=125, threshold=3))
        layer.original = img
        layer.apply_adjustments()
        self._update_composite()

    def _replace_background(self) -> None:
        """Replace the background of the current layer outside the mask.

        This function uses the layer's mask to identify the subject. The
        user chooses a replacement colour; all pixels where the mask is
        mostly transparent (value < 128) are filled with that colour.
        """
        if self.current_layer_index is None:
            return
        # Ask the user for a replacement colour
        color = colorchooser.askcolor(title="Choose background colour")
        if not color or not color[0]:
            return
        rgb = tuple(int(c) for c in color[0])
        self._save_history()
        layer = self.layers[self.current_layer_index]
        orig = layer.original.copy()
        # Invert mask: areas with value < 128 will be replaced
        mask_inv = layer.mask.point(lambda v: 255 if v < 128 else 0)
        # Create solid colour image
        bg = Image.new("RGBA", orig.size, rgb + (255,))
        # Composite: fill transparent areas with bg using mask_inv
        orig.paste(bg, (0, 0), mask_inv)
        layer.original = orig
        layer.apply_adjustments()
        self._update_composite()

    def _export_preset(self, target_w: int, target_h: int) -> None:
        """Export the current composite image to a predefined size.

        The resulting image is resized to fill the target dimensions,
        cropping to preserve aspect ratio.  A save dialog prompts for
        the filename.  Use this to quickly generate social media
        friendly images.

        :param target_w: target width in pixels
        :param target_h: target height in pixels
        """
        if not self.layers:
            messagebox.showinfo("No image", "There is nothing to export.")
            return
        composite = self._create_composite_image()
        # Fit image to target size with cropping while preserving aspect ratio
        try:
            from PIL import ImageOps
            export_img = ImageOps.fit(composite, (target_w, target_h), method=Image.BICUBIC)
        except Exception:
            export_img = composite.resize((target_w, target_h), resample=Image.BICUBIC)
        filetypes = [("PNG", "*.png"), ("JPEG", "*.jpg"), ("All files", "*.*")]
        filepath = filedialog.asksaveasfilename(title="Export Image", defaultextension=".png", filetypes=filetypes)
        if not filepath:
            return
        try:
            export_img.save(filepath)
            messagebox.showinfo("Exported", f"Image exported to {filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save exported image: {e}")

    def _preview_and_apply_filter(self, filter_name: str) -> None:
        """Preview a filter on the current layer before applying it.

        A downscaled version of the selected layer is shown with the filter
        applied.  The user can decide whether to commit the change or
        cancel it.  If cancelled, no modification is made.

        :param filter_name: name of the filter to apply (grayscale, blur, etc.)
        """
        if self.current_layer_index is None:
            return
        layer = self.layers[self.current_layer_index]
        # Make a copy of the original layer image for preview
        preview_img = layer.original.copy()
        temp_layer = Layer(preview_img.copy(), "preview")
        try:
            temp_layer.apply_filter(filter_name)
        except Exception as e:
            messagebox.showerror("Filter error", str(e))
            return
        preview_img = temp_layer.original
        # Downscale preview to fit a small window while preserving aspect ratio
        max_preview_size = 300
        w, h = preview_img.size
        scale = min(max_preview_size / w, max_preview_size / h, 1.0)
        prev = preview_img.copy()
        if scale < 1.0:
            prev = prev.resize((int(w * scale), int(h * scale)), resample=Image.BICUBIC)
        # Create preview window
        win = tk.Toplevel(self)
        win.title(f"Preview: {filter_name}")
        win.configure(bg="#3a3a3a")
        # Display image
        photo = ImageTk.PhotoImage(prev)
        img_label = tk.Label(win, image=photo)
        img_label.image = photo  # keep reference
        img_label.pack(padx=10, pady=10)
        # Buttons
        btn_frame = tk.Frame(win, bg="#3a3a3a")
        btn_frame.pack(pady=5)
        def apply_change():
            # Apply filter for real and update
            self._apply_filter(filter_name)
            win.destroy()
        def cancel():
            win.destroy()
        apply_btn = tk.Button(btn_frame, text="Apply", command=apply_change, bg="#5c5c5c", fg="white")
        apply_btn.pack(side=tk.LEFT, padx=5)
        cancel_btn = tk.Button(btn_frame, text="Cancel", command=cancel, bg="#5c5c5c", fg="white")
        cancel_btn.pack(side=tk.LEFT, padx=5)

    # ------------------------------------------------------------------
    # Tools (brush and text)
    # ------------------------------------------------------------------
    def _select_brush(self):
        """Activate the brush tool and prompt user for colour and size."""
        self.current_tool = "brush"
        # Ask colour
        color = colorchooser.askcolor(title="Choose brush colour", initialcolor=self.brush_color)
        if color and color[1]:
            self.brush_color = color[1]
        # Ask size
        size = simpledialog.askinteger("Brush Size", "Enter brush size (1-100)", initialvalue=self.brush_size, minvalue=1, maxvalue=100)
        if size:
            self.brush_size = size
        # Highlight selected tool
        self._highlight_tool()

    def _select_eraser(self):
        """Activate the eraser tool and prompt user for size."""
        self.current_tool = "eraser"
        size = simpledialog.askinteger("Eraser Size", "Enter eraser size (1-100)", initialvalue=self.brush_size, minvalue=1, maxvalue=100)
        if size:
            self.brush_size = size
        self._highlight_tool()

    def _select_move(self):
        """Activate the move tool to reposition the selected layer."""
        self.current_tool = "move"
        self._drag_prev = None
        self._highlight_tool()

    def _select_mask(self):
        """Activate the mask editing tool or create special masks.

        Users can choose between painting the mask manually (as before) or
        generating a linear, radial or patterned mask.  Painting requires
        selecting hide/reveal mode and brush size.  Generated masks are
        applied immediately and the tool is reset.
        """
        # Choose mask type
        mtype = simpledialog.askstring(
            "Mask Type",
            "Choose mask type (paint, linear, radial, pattern, ellipse, ring, diagonal, noise, triangle, adjust, filter):",
            initialvalue="paint",
        )
        if mtype is None:
            return
        mtype = mtype.strip().lower()
        if mtype == "paint":
            # Ask hide or reveal
            choice = simpledialog.askstring(
                "Mask Mode",
                "Enter mask mode: hide or reveal",
                initialvalue="hide",
            )
            if choice is None:
                return
            mode = choice.strip().lower()
            if mode not in ("hide", "reveal"):
                messagebox.showinfo("Invalid mode", "Mask mode must be 'hide' or 'reveal'")
                return
            self.mask_mode = mode
            # Ask brush size
            size = simpledialog.askinteger(
                "Mask Brush Size",
                "Enter mask brush size (1-200)",
                initialvalue=self.brush_size,
                minvalue=1,
                maxvalue=200,
            )
            if size:
                self.brush_size = size
            self.current_tool = "mask"
            self._highlight_tool()
        else:
            if self.current_layer_index is None:
                return
            layer = self.layers[self.current_layer_index]
            # Some special operations adjust existing mask rather than creating new
            if mtype in ("adjust", "filter"):
                # Save history
                self._save_history()
                w, h = layer.mask.size
                mask = layer.mask.copy()
                if mtype == "adjust":
                    # Ask which adjustment: lighten, darken, invert, threshold
                    adj = simpledialog.askstring(
                        "Adjust Mask",
                        "Adjustment (lighten, darken, invert, contrast):",
                        initialvalue="lighten",
                    )
                    if adj is None:
                        return
                    adj = adj.strip().lower()
                    if adj == "lighten":
                        factor = simpledialog.askfloat(
                            "Lighten Amount",
                            "Enter lighten amount (0-1, where 0 no change, 1 full white):",
                            initialvalue=0.2,
                            minvalue=0.0,
                            maxvalue=1.0,
                        )
                        if factor is None:
                            return
                        # lighten by factor: mask + factor*(255-mask)
                        mask = mask.point(lambda i, f=factor: int(i + f * (255 - i)))
                    elif adj == "darken":
                        factor = simpledialog.askfloat(
                            "Darken Amount",
                            "Enter darken amount (0-1, where 0 no change, 1 full black):",
                            initialvalue=0.2,
                            minvalue=0.0,
                            maxvalue=1.0,
                        )
                        if factor is None:
                            return
                        mask = mask.point(lambda i, f=factor: int(i * (1 - f)))
                    elif adj == "invert":
                        mask = ImageChops.invert(mask)
                    elif adj == "contrast":
                        # Enhance contrast: scale difference from mid grey
                        factor = simpledialog.askfloat(
                            "Contrast Factor",
                            "Enter contrast factor (>1 increases contrast, <1 decreases)",
                            initialvalue=1.5,
                            minvalue=0.1,
                            maxvalue=5.0,
                        )
                        if factor is None:
                            return
                        def adjust_contrast(p, f):
                            # map 0-255 to -1 to 1
                            np = p / 255.0
                            np = (np - 0.5) * f + 0.5
                            return int(max(0, min(255, np * 255)))
                        mask = mask.point(lambda i, f=factor: adjust_contrast(i, f))
                    else:
                        messagebox.showinfo("Adjustment", "Unsupported adjustment type.")
                        return
                    layer.mask = mask
                    layer.apply_adjustments()
                    self._update_composite()
                    return
                elif mtype == "filter":
                    # Ask filter name for mask: blur, sharpen, smooth, emboss
                    filt = simpledialog.askstring(
                        "Mask Filter",
                        "Mask filter (blur, sharpen, smooth, emboss):",
                        initialvalue="blur",
                    )
                    if filt is None:
                        return
                    filt = filt.strip().lower()
                    if filt == "blur":
                        mask = mask.filter(ImageFilter.GaussianBlur(radius=3))
                    elif filt == "sharpen":
                        mask = mask.filter(ImageFilter.UnsharpMask(radius=2, percent=200, threshold=3))
                    elif filt == "smooth":
                        mask = mask.filter(ImageFilter.SMOOTH_MORE)
                    elif filt == "emboss":
                        mask = mask.filter(ImageFilter.EMBOSS)
                    else:
                        messagebox.showinfo("Mask Filter", "Unsupported mask filter")
                        return
                    layer.mask = mask
                    layer.apply_adjustments()
                    self._update_composite()
                    return
            # For generated masks, ask hide or reveal
            choice = simpledialog.askstring(
                "Mask Mode",
                "Enter mask mode: hide or reveal",
                initialvalue="hide",
            )
            if choice is None:
                return
            hide = choice.strip().lower() == "hide"
            # Save history
            self._save_history()
            w, h = layer.mask.size
            mask = Image.new("L", (w, h), 0)
            if mtype == "linear":
                # Ask orientation
                orientation = simpledialog.askstring(
                    "Gradient Orientation",
                    "Enter orientation (horizontal or vertical):",
                    initialvalue="horizontal",
                )
                if orientation is None:
                    return
                orientation = orientation.strip().lower()
                if orientation.startswith("h"):
                    for x in range(w):
                        t = x / (w - 1) if w > 1 else 0
                        val = int(255 * t)
                        if hide:
                            val = 255 - val
                        for y in range(h):
                            mask.putpixel((x, y), val)
                else:
                    for y in range(h):
                        t = y / (h - 1) if h > 1 else 0
                        val = int(255 * t)
                        if hide:
                            val = 255 - val
                        for x in range(w):
                            mask.putpixel((x, y), val)
            elif mtype == "radial":
                cx = w / 2
                cy = h / 2
                max_r = math.hypot(cx, cy)
                for y in range(h):
                    for x in range(w):
                        dx = x - cx
                        dy = y - cy
                        r = math.hypot(dx, dy)
                        t = r / max_r if max_r > 0 else 0
                        if hide:
                            val = int(255 * (1 - t))
                        else:
                            val = int(255 * t)
                        val = max(0, min(255, val))
                        mask.putpixel((x, y), val)
            elif mtype == "pattern":
                # Ask pattern type
                ptype = simpledialog.askstring(
                    "Pattern Type",
                    "Enter pattern (stripes, checker, diagonal):",
                    initialvalue="stripes",
                )
                if ptype is None:
                    return
                ptype = ptype.strip().lower()
                stripe_width = simpledialog.askinteger(
                    "Pattern Size",
                    "Enter pattern size (pixels):",
                    initialvalue=20,
                    minvalue=1,
                    maxvalue=200,
                )
                if not stripe_width:
                    stripe_width = 20
                for y in range(h):
                    for x in range(w):
                        if ptype.startswith("diag"):
                            band = ((x + y) // stripe_width) % 2
                        elif ptype.startswith("str"):
                            band = (x // stripe_width) % 2
                        else:
                            band = ((x // stripe_width) + (y // stripe_width)) % 2
                        val = 0 if (band == 0) ^ hide else 255
                        mask.putpixel((x, y), val)
            elif mtype == "ellipse":
                # Create elliptical gradient or solid; ask solid or gradient
                solid = messagebox.askyesno("Ellipse Mask", "Solid ellipse? (Yes=solid, No=gradient)")
                for y in range(h):
                    for x in range(w):
                        # normalised distances relative to centre
                        nx = (x - w / 2) / (w / 2)
                        ny = (y - h / 2) / (h / 2)
                        dist = nx * nx + ny * ny
                        if solid:
                            inside = dist <= 1.0
                            val = 0 if inside ^ hide else 255
                        else:
                            # gradient: distance squared -> alpha
                            # inside centre (dist=0) -> full effect; at edge (dist=1) -> 0
                            t = min(1.0, dist)
                            val = int(255 * (1 - t)) if hide else int(255 * t)
                        mask.putpixel((x, y), val)
            elif mtype == "ring":
                # Ring shaped mask; ask inner and outer radius fractions
                inner_ratio = simpledialog.askfloat(
                    "Inner Radius",
                    "Enter inner radius fraction (0-1)",
                    initialvalue=0.3,
                    minvalue=0.0,
                    maxvalue=1.0,
                )
                if inner_ratio is None:
                    return
                outer_ratio = simpledialog.askfloat(
                    "Outer Radius",
                    "Enter outer radius fraction (0-1, > inner)",
                    initialvalue=0.6,
                    minvalue=inner_ratio,
                    maxvalue=1.0,
                )
                if outer_ratio is None:
                    return
                cx = w / 2
                cy = h / 2
                max_rad = (min(w, h) / 2) * outer_ratio
                min_rad = (min(w, h) / 2) * inner_ratio
                for y in range(h):
                    for x in range(w):
                        dx = x - cx
                        dy = y - cy
                        dist = math.hypot(dx, dy)
                        if min_rad <= dist <= max_rad:
                            val = 0 if hide else 255
                        else:
                            val = 255 if hide else 0
                        mask.putpixel((x, y), val)
            elif mtype == "diagonal":
                # Diagonal gradient from top-left to bottom-right
                for y in range(h):
                    for x in range(w):
                        t = (x + y) / (w + h - 2) if (w + h) > 2 else 0
                        val = int(255 * t)
                        if hide:
                            val = 255 - val
                        mask.putpixel((x, y), val)
            elif mtype == "noise":
                # Random noise mask; ask density or threshold
                density = simpledialog.askinteger(
                    "Noise Mask",
                    "Enter density percentage for noise (0-100)",
                    initialvalue=50,
                    minvalue=0,
                    maxvalue=100,
                )
                if density is None:
                    density = 50
                import random
                for y in range(h):
                    for x in range(w):
                        r = random.randint(0, 100)
                        if r < density:
                            val = 0 if hide else 255
                        else:
                            val = 255 if hide else 0
                        mask.putpixel((x, y), val)
            elif mtype == "triangle":
                # Triangular gradient; ask orientation (up, down, left, right)
                orient = simpledialog.askstring(
                    "Triangle Orientation",
                    "Enter orientation (up, down, left, right)",
                    initialvalue="up",
                )
                if orient is None:
                    return
                orient = orient.strip().lower()
                if orient == "up":
                    # Gradient from bottom to top (0 at bottom, 255 at top if hide)
                    for y in range(h):
                        t = 1 - (y / (h - 1) if h > 1 else 0)
                        val_row = int(255 * t)
                        if not hide:
                            val_row = 255 - val_row
                        for x in range(w):
                            mask.putpixel((x, y), val_row)
                elif orient == "down":
                    for y in range(h):
                        t = y / (h - 1) if h > 1 else 0
                        val_row = int(255 * t)
                        if hide:
                            val_row = 255 - val_row
                        for x in range(w):
                            mask.putpixel((x, y), val_row)
                elif orient == "left":
                    for x in range(w):
                        t = 1 - (x / (w - 1) if w > 1 else 0)
                        val_col = int(255 * t)
                        if not hide:
                            val_col = 255 - val_col
                        for y in range(h):
                            mask.putpixel((x, y), val_col)
                else:
                    for x in range(w):
                        t = x / (w - 1) if w > 1 else 0
                        val_col = int(255 * t)
                        if hide:
                            val_col = 255 - val_col
                        for y in range(h):
                            mask.putpixel((x, y), val_col)
            else:
                messagebox.showinfo("Unknown mask type", f"Mask type '{mtype}' is not supported.")
                return
            # Apply mask to layer
            layer.mask = mask
            layer.apply_adjustments()
            self._update_composite()
            # Reset tool
            self.current_tool = None
            self._highlight_tool()

    def _select_crop(self):
        """Activate the crop tool to select an area to keep."""
        self.current_tool = "crop"
        # Remove any existing rectangle
        self._crop_rect_id = None
        self._crop_start = None
        self._highlight_tool()

    def _select_select_tool(self):
        """Activate the select tool for editing layer properties via clicking."""
        self.current_tool = "select"
        self._highlight_tool()

    def _select_text_tool(self):
        """Activate the text tool and prompt user for content, font and colour."""
        self.current_tool = "text"
        # Ask for text content
        text = simpledialog.askstring("Text", "Enter text to add:")
        if text is None or text == "":
            self.current_tool = None
            return
        self.pending_text = text
        # Ask font size
        size = simpledialog.askinteger("Font Size", "Enter font size (8-200)", initialvalue=32, minvalue=8, maxvalue=200)
        if size:
            self.pending_font_size = size
        else:
            self.pending_font_size = 32
        # Ask font name or path
        font_name = simpledialog.askstring("Font", "Enter font family or path (leave blank for default):")
        if font_name:
            self.pending_font_name = font_name.strip()
        else:
            self.pending_font_name = None
        # Ask colour
        color = colorchooser.askcolor(title="Choose text colour", initialcolor="#ffffff")
        if color and color[1]:
            self.pending_text_color = color[1]
        else:
            self.pending_text_color = "#ffffff"
        # Wait for click on canvas to place text
        messagebox.showinfo("Place Text", "Click on the image to place the text.")
        self._highlight_tool()

    def _select_filter_region(self):
        """Activate tool to select a rectangular region and apply a filter only within that region."""
        self.current_tool = 'filter_region'
        # Variables to track selection rectangle
        self._filter_region_start = None
        self._filter_rect_id = None
        self._highlight_tool()

    # ------------------------------------------------------------------
    # Canvas events
    # ------------------------------------------------------------------
    def _on_canvas_press(self, event):
        """Handle mouse press events on the canvas."""
        if self.current_layer_index is None:
            return
        # If drawing or erasing, save state at start of stroke
        if self.current_tool in ("brush", "eraser"):
            self._save_history()
            self._history_saved_for_stroke = True
            self._drag_prev = (event.x, event.y)
            if self.current_tool == "brush":
                self._paint_at(event.x, event.y)
            elif self.current_tool == "eraser":
                self._erase_at(event.x, event.y)
        elif self.current_tool == "text":
            # Save history before adding text
            self._save_history()
            self._add_text(event.x, event.y)
            # After placing text, reset tool
            self.current_tool = None
        elif self.current_tool == "move":
            # Save history at beginning of move
            self._save_history()
            self._history_saved_for_stroke = True
            self._drag_prev = (event.x, event.y)
            # Record initial offset for the layer
            self._move_start_offset = self.layers[self.current_layer_index].offset
        elif self.current_tool == "mask":
            # Save history at beginning of mask painting
            self._save_history()
            self._history_saved_for_stroke = True
            self._drag_prev = (event.x, event.y)
            # Paint initial dot on mask
            self._mask_at(event.x, event.y)
        elif self.current_tool == "crop":
            # Save history (crop will crop on release)
            self._save_history()
            self._history_saved_for_stroke = True
            self._crop_start = (event.x, event.y)
            # Create rectangle overlay
            self._crop_rect_id = self.canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="yellow", dash=(4, 2))
        elif self.current_tool == "select":
            # Select the topmost layer at this point and open a property window
            self._select_layer_at(event.x, event.y)
            self._open_properties_window()
        elif self.current_tool == "filter_region":
            # Save history: filter will be applied on release
            self._save_history()
            self._history_saved_for_stroke = True
            self._filter_region_start = (event.x, event.y)
            # Create rectangle overlay for region selection
            self._filter_rect_id = self.canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="#00ff00", dash=(4, 2))
        else:
            # For future tools (e.g., selection) we could handle here
            pass

    def _on_canvas_drag(self, event):
        if self.current_layer_index is None:
            return
        if self.current_tool == "brush" and self._drag_prev:
            # Draw line from previous point to current
            x0, y0 = self._drag_prev
            x1, y1 = event.x, event.y
            self._paint_line(x0, y0, x1, y1)
            self._drag_prev = (x1, y1)
        elif self.current_tool == "eraser" and self._drag_prev:
            x0, y0 = self._drag_prev
            x1, y1 = event.x, event.y
            self._erase_line(x0, y0, x1, y1)
            self._drag_prev = (x1, y1)
        elif self.current_tool == "move" and self._drag_prev:
            # Move layer by delta from starting position
            x0, y0 = self._drag_prev
            dx = event.x - x0
            dy = event.y - y0
            # Update layer offset relative to initial offset
            ox0, oy0 = self._move_start_offset
            self.layers[self.current_layer_index].offset = (ox0 + dx, oy0 + dy)
            self._update_composite()
        elif self.current_tool == "mask" and self._drag_prev:
            x0, y0 = self._drag_prev
            x1, y1 = event.x, event.y
            self._mask_line(x0, y0, x1, y1)
            self._drag_prev = (x1, y1)
        elif self.current_tool == "crop" and self._crop_rect_id is not None and self._crop_start:
            # Update cropping rectangle overlay
            x0, y0 = self._crop_start
            self.canvas.coords(self._crop_rect_id, x0, y0, event.x, event.y)
        elif self.current_tool == "filter_region" and self._filter_rect_id is not None and self._filter_region_start:
            # Update overlay rectangle for filter region selection
            x0, y0 = self._filter_region_start
            self.canvas.coords(self._filter_rect_id, x0, y0, event.x, event.y)

    def _on_canvas_release(self, event):
        # End drawing or other stroke
        if self.current_tool == "move":
            # After move, nothing else to do (history saved at press)
            pass
        elif self.current_tool == "mask":
            # mask painting done
            pass
        elif self.current_tool == "crop":
            # Perform crop based on rectangle
            if self._crop_rect_id is not None and self._crop_start:
                x0, y0 = self._crop_start
                x1, y1 = event.x, event.y
                self.canvas.delete(self._crop_rect_id)
                self._crop_rect_id = None
                self._perform_crop(x0, y0, x1, y1)
            self._crop_start = None
            # Reset tool after cropping
            self.current_tool = None
        elif self.current_tool == "filter_region":
            # Apply filter to the selected region
            if self._filter_rect_id is not None and getattr(self, '_filter_region_start', None):
                x0, y0 = self._filter_region_start
                x1, y1 = event.x, event.y
                # Remove overlay
                self.canvas.delete(self._filter_rect_id)
                self._filter_rect_id = None
                # Determine bounding box on canvas
                left = int(min(x0, x1))
                upper = int(min(y0, y1))
                right = int(max(x0, x1))
                lower = int(max(y0, y1))
                if right > left and lower > upper and self.current_layer_index is not None:
                    # Ask for filter name
                    filter_options = ["grayscale", "invert", "blur", "sharpen", "emboss", "edge", "contour", "detail", "smooth", "liquify", "sepia"]
                    filter_name = simpledialog.askstring("Filter", f"Enter filter to apply {filter_options}")
                    if filter_name:
                        filter_name = filter_name.strip().lower()
                        if filter_name not in filter_options:
                            messagebox.showinfo("Filter", "Unsupported filter name.")
                        else:
                            # Convert canvas coords to layer coords
                            layer = self.layers[self.current_layer_index]
                            ox, oy = layer.offset
                            region_box = (left - int(ox), upper - int(oy), right - int(ox), lower - int(oy))
                            try:
                                layer.apply_filter_to_region(filter_name, region_box)
                            except Exception as e:
                                messagebox.showerror("Error", str(e))
                            self._update_composite()
                # Reset selection variables
                self._filter_region_start = None
            # Reset tool after applying filter
            self.current_tool = None
        self._drag_prev = None
        # Reset history flag after stroke
        self._reset_history_flag()

    # ------------------------------------------------------------------
    # Drawing helpers
    # ------------------------------------------------------------------
    def _paint_at(self, x: int, y: int):
        """Draw a dot at the given coordinates on the current layer."""
        layer = self.layers[self.current_layer_index]
        draw = ImageDraw.Draw(layer.original)
        # Draw circle on original to allow reapplication of filters/brightness
        r = self.brush_size / 2
        draw.ellipse([(x - r, y - r), (x + r, y + r)], fill=self.brush_color)
        # Apply brightness and alpha to update layer.image
        layer.apply_adjustments()
        self._update_composite()

    def _paint_line(self, x0: int, y0: int, x1: int, y1: int):
        """Draw a thick line between two points on the current layer."""
        layer = self.layers[self.current_layer_index]
        draw = ImageDraw.Draw(layer.original)
        draw.line([(x0, y0), (x1, y1)], fill=self.brush_color, width=self.brush_size)
        # If brush size > 1, draw circles at endpoints to avoid gaps
        r = self.brush_size / 2
        draw.ellipse([(x0 - r, y0 - r), (x0 + r, y0 + r)], fill=self.brush_color)
        draw.ellipse([(x1 - r, y1 - r), (x1 + r, y1 + r)], fill=self.brush_color)
        layer.apply_adjustments()
        self._update_composite()

    def _add_text(self, x: int, y: int):
        """Render pending text at the specified location on the current layer."""
        layer = self.layers[self.current_layer_index]
        # Determine a reasonable font
        # Choose font: use user‑provided font name/path if available
        font = None
        if getattr(self, 'pending_font_name', None):
            try:
                font = ImageFont.truetype(self.pending_font_name, self.pending_font_size)
            except Exception:
                # Could not load requested font, fall back later
                font = None
        if font is None:
            # Fallback to default font
            try:
                font = ImageFont.truetype("arial.ttf", self.pending_font_size)
            except Exception:
                font = ImageFont.load_default()
        draw = ImageDraw.Draw(layer.original)
        draw.text((x, y), self.pending_text, fill=self.pending_text_color, font=font)
        layer.apply_adjustments()
        self._update_composite()

    # ------------------------------------------------------------------
    # Mask painting helpers
    # ------------------------------------------------------------------
    def _mask_at(self, x: int, y: int) -> None:
        """Paint on the current layer's mask at a single point.

        When mask_mode is 'hide', this draws black (0) to hide pixels.
        When mask_mode is 'reveal', it draws white (255) to reveal.
        """
        if self.current_layer_index is None:
            return
        layer = self.layers[self.current_layer_index]
        # Determine value to paint
        value = 0 if getattr(self, 'mask_mode', 'hide') == 'hide' else 255
        r = self.brush_size / 2
        draw = ImageDraw.Draw(layer.mask)
        draw.ellipse([(x - r, y - r), (x + r, y + r)], fill=value)
        layer.apply_adjustments()
        self._update_composite()

    def _mask_line(self, x0: int, y0: int, x1: int, y1: int) -> None:
        """Paint on the mask along a line by interpolating points."""
        dx = x1 - x0
        dy = y1 - y0
        dist = (dx * dx + dy * dy) ** 0.5
        steps = int(dist / (self.brush_size / 2)) + 1
        for i in range(steps + 1):
            t = i / steps
            x = int(x0 + dx * t)
            y = int(y0 + dy * t)
            self._mask_at(x, y)

    # ------------------------------------------------------------------
    # Cropping helper
    # ------------------------------------------------------------------
    def _perform_crop(self, x0: int, y0: int, x1: int, y1: int) -> None:
        """Crop all layers to the rectangular region defined by two points."""
        if not self.layers:
            return
        # Determine bounding box and clamp within image bounds
        x0_clamped = max(0, min(self.canvas.winfo_width(), x0))
        y0_clamped = max(0, min(self.canvas.winfo_height(), y0))
        x1_clamped = max(0, min(self.canvas.winfo_width(), x1))
        y1_clamped = max(0, min(self.canvas.winfo_height(), y1))
        left = int(min(x0_clamped, x1_clamped))
        upper = int(min(y0_clamped, y1_clamped))
        right = int(max(x0_clamped, x1_clamped))
        lower = int(max(y0_clamped, y1_clamped))
        if right - left <= 0 or lower - upper <= 0:
            return
        box = (left, upper, right, lower)
        # Crop each layer's original and mask, adjusting offset
        for layer in self.layers:
            # Adjust offset: remove region from left/top
            ox, oy = layer.offset
            new_offset = (ox - left, oy - upper)
            # Crop original and mask to bounding box considering offset
            # Create a copy of the image with offset applied
            # For cropping, we need to align the crop box relative to the layer image
            # The displayed position of layer pixel (img_x, img_y) on canvas is (img_x + ox, img_y + oy)
            # So pixel corresponds to original coordinate (img_x) = canvas_x - ox.
            # Therefore cropping region for original is box shifted by (-ox, -oy)
            shift_box = (box[0] - ox, box[1] - oy, box[2] - ox, box[3] - oy)
            # Crop original and mask
            layer.original = layer.original.crop(shift_box)
            layer.mask = layer.mask.crop(shift_box)
            layer.offset = new_offset
            layer.apply_adjustments()
        # Update canvas size
        new_width = right - left
        new_height = lower - upper
        self.canvas.config(width=new_width, height=new_height)
        self._refresh_layer_list()
        self._update_composite()

    # ------------------------------------------------------------------
    # Selection tool helpers
    # ------------------------------------------------------------------
    def _select_layer_at(self, canvas_x: int, canvas_y: int) -> None:
        """Set current_layer_index to the topmost visible layer at the given canvas coordinates."""
        # Iterate top to bottom
        for idx in reversed(range(len(self.layers))):
            layer = self.layers[idx]
            if not layer.visible:
                continue
            # Calculate relative coordinates inside the layer
            ox, oy = layer.offset
            rel_x = canvas_x - int(ox)
            rel_y = canvas_y - int(oy)
            if rel_x < 0 or rel_y < 0 or rel_x >= layer.image.width or rel_y >= layer.image.height:
                continue
            # Check alpha at this pixel
            try:
                pixel = layer.image.getpixel((int(rel_x), int(rel_y)))
            except Exception:
                continue
            if len(pixel) == 4 and pixel[3] > 0:
                self.current_layer_index = idx
                # Update sliders to selected layer
                self.alpha_slider.set(layer.alpha)
                self.brightness_slider.set(layer.brightness)
                if hasattr(self, 'contrast_slider'):
                    self.contrast_slider.set(layer.contrast)
                if hasattr(self, 'color_slider'):
                    self.color_slider.set(layer.color)
                self._refresh_layer_list()
                return

    def _open_properties_window(self) -> None:
        """Open a small window with sliders to edit current layer's properties."""
        if self.current_layer_index is None:
            return
        layer = self.layers[self.current_layer_index]
        # Create new top-level window
        prop_win = tk.Toplevel(self)
        prop_win.title(f"Properties - {layer.name}")
        prop_win.configure(bg="#3a3a3a")
        # Sliders for alpha, brightness, contrast, colour
        def on_prop_change(val, prop):
            # Save history only first time any property is changed
            if not hasattr(on_prop_change, 'saved'):
                self._save_history()
                on_prop_change.saved = True
            if prop == 'alpha':
                layer.alpha = float(alpha_scale.get())
            elif prop == 'brightness':
                layer.brightness = float(bright_scale.get())
            elif prop == 'contrast':
                layer.contrast = float(contrast_scale.get())
            elif prop == 'color':
                layer.color = float(color_scale.get())
            elif prop == 'gamma':
                layer.gamma = float(gamma_scale.get())
            elif prop == 'red':
                layer.red = float(red_scale.get())
            elif prop == 'green':
                layer.green = float(green_scale.get())
            elif prop == 'blue':
                layer.blue = float(blue_scale.get())
            layer.apply_adjustments()
            self._update_composite()
        # Create scales
        tk.Label(prop_win, text="Opacity", bg="#3a3a3a", fg="white").pack(pady=2)
        alpha_scale = tk.Scale(prop_win, from_=0, to=1, resolution=0.01, orient=tk.HORIZONTAL, bg="#3a3a3a", fg="white", length=200)
        alpha_scale.set(layer.alpha)
        alpha_scale.config(command=lambda v: on_prop_change(v, 'alpha'))
        alpha_scale.pack(pady=2)
        tk.Label(prop_win, text="Brightness", bg="#3a3a3a", fg="white").pack(pady=2)
        bright_scale = tk.Scale(prop_win, from_=0.1, to=2, resolution=0.05, orient=tk.HORIZONTAL, bg="#3a3a3a", fg="white", length=200)
        bright_scale.set(layer.brightness)
        bright_scale.config(command=lambda v: on_prop_change(v, 'brightness'))
        bright_scale.pack(pady=2)
        tk.Label(prop_win, text="Contrast", bg="#3a3a3a", fg="white").pack(pady=2)
        contrast_scale = tk.Scale(prop_win, from_=0.1, to=2, resolution=0.05, orient=tk.HORIZONTAL, bg="#3a3a3a", fg="white", length=200)
        contrast_scale.set(layer.contrast)
        contrast_scale.config(command=lambda v: on_prop_change(v, 'contrast'))
        contrast_scale.pack(pady=2)
        tk.Label(prop_win, text="Color", bg="#3a3a3a", fg="white").pack(pady=2)
        color_scale = tk.Scale(prop_win, from_=0.1, to=2, resolution=0.05, orient=tk.HORIZONTAL, bg="#3a3a3a", fg="white", length=200)
        color_scale.set(layer.color)
        color_scale.config(command=lambda v: on_prop_change(v, 'color'))
        color_scale.pack(pady=2)
        # Gamma slider
        tk.Label(prop_win, text="Gamma", bg="#3a3a3a", fg="white").pack(pady=2)
        gamma_scale = tk.Scale(prop_win, from_=0.2, to=3.0, resolution=0.05, orient=tk.HORIZONTAL, bg="#3a3a3a", fg="white", length=200)
        gamma_scale.set(layer.gamma)
        gamma_scale.config(command=lambda v: on_prop_change(v, 'gamma'))
        gamma_scale.pack(pady=2)
        # Red, Green, Blue channel sliders for selective colour adjustments
        tk.Label(prop_win, text="Red", bg="#3a3a3a", fg="white").pack(pady=2)
        red_scale = tk.Scale(prop_win, from_=0.0, to=3.0, resolution=0.05, orient=tk.HORIZONTAL, bg="#3a3a3a", fg="white", length=200)
        red_scale.set(layer.red)
        red_scale.config(command=lambda v: on_prop_change(v, 'red'))
        red_scale.pack(pady=2)
        tk.Label(prop_win, text="Green", bg="#3a3a3a", fg="white").pack(pady=2)
        green_scale = tk.Scale(prop_win, from_=0.0, to=3.0, resolution=0.05, orient=tk.HORIZONTAL, bg="#3a3a3a", fg="white", length=200)
        green_scale.set(layer.green)
        green_scale.config(command=lambda v: on_prop_change(v, 'green'))
        green_scale.pack(pady=2)
        tk.Label(prop_win, text="Blue", bg="#3a3a3a", fg="white").pack(pady=2)
        blue_scale = tk.Scale(prop_win, from_=0.0, to=3.0, resolution=0.05, orient=tk.HORIZONTAL, bg="#3a3a3a", fg="white", length=200)
        blue_scale.set(layer.blue)
        blue_scale.config(command=lambda v: on_prop_change(v, 'blue'))
        blue_scale.pack(pady=2)
        # Close button
        def close_window():
            prop_win.destroy()
            # Reset property change flag for next opening
            if hasattr(on_prop_change, 'saved'):
                del on_prop_change.saved
        tk.Button(prop_win, text="Close", command=close_window, bg="#5c5c5c", fg="white").pack(pady=5)

    def _erase_at(self, x: int, y: int) -> None:
        """Erase a circular region at the given coordinates by setting alpha to 0."""
        layer = self.layers[self.current_layer_index]
        base_size = layer.original.size
        r = self.brush_size / 2
        # Create mask for eraser circle
        mask = Image.new("L", base_size, 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.ellipse([(x - r, y - r), (x + r, y + r)], fill=255)
        # Create transparent colour (RGBA)
        transparent_img = Image.new("RGBA", base_size, (0, 0, 0, 0))
        # Paste transparent colour over original using mask
        layer.original.paste(transparent_img, (0, 0), mask)
        layer.apply_adjustments()
        self._update_composite()

    def _erase_line(self, x0: int, y0: int, x1: int, y1: int) -> None:
        """Erase along a line between two points using multiple circles to avoid gaps."""
        # Draw along line by interpolating points at small intervals
        layer = self.layers[self.current_layer_index]
        # approximate number of steps based on distance and brush size
        dx = x1 - x0
        dy = y1 - y0
        dist = (dx * dx + dy * dy) ** 0.5
        steps = int(dist / (self.brush_size / 2)) + 1
        for i in range(steps + 1):
            t = i / steps
            x = int(x0 + dx * t)
            y = int(y0 + dy * t)
            self._erase_at(x, y)

    # ------------------------------------------------------------------
    # Collage and composition helpers
    # ------------------------------------------------------------------
    def _create_collage_from_files(self) -> None:
        """Prompt user to select multiple images and arrange them into a collage.

        The user is asked to choose one or more image files.  They can then
        specify the number of columns, cell size and background colour.  A new
        document is created (optionally replacing the current one) and each
        selected image becomes a layer positioned within a grid.  Images may
        be scaled to fit the cell dimensions.
        """
        # Ask for image files
        filetypes = [("Image files", "*.png;*.jpg;*.jpeg;*.bmp;*.gif"), ("All files", "*.*")]
        paths = filedialog.askopenfilenames(title="Select Images for Collage", filetypes=filetypes)
        if not paths:
            return
        num_images = len(paths)
        # Ask number of columns
        cols = simpledialog.askinteger(
            "Columns",
            "Enter number of columns for collage (1-10)",
            initialvalue=min(3, num_images),
            minvalue=1,
            maxvalue=max(10, num_images),
        )
        if cols is None or cols <= 0:
            return
        rows = (num_images + cols - 1) // cols
        # Load first image to determine default cell size
        try:
            first_img = Image.open(paths[0]).convert("RGBA")
        except Exception as e:
            messagebox.showerror("Error", f"Unable to open image: {e}")
            return
        default_w, default_h = first_img.size
        # Ask cell width and height
        cell_w = simpledialog.askinteger(
            "Cell Width",
            "Enter width for each collage cell (pixels)",
            initialvalue=default_w,
            minvalue=1,
        )
        if cell_w is None:
            return
        cell_h = simpledialog.askinteger(
            "Cell Height",
            "Enter height for each collage cell (pixels)",
            initialvalue=default_h,
            minvalue=1,
        )
        if cell_h is None:
            return
        # Ask whether to start a new project (clearing existing layers)
        replace = messagebox.askyesno(
            "New Document?",
            "Create collage in a new document?\nThis will discard current layers.",
        )
        # Ask background colour for collage
        bg_colour = colorchooser.askcolor(title="Choose background colour for collage", initialcolor="#ffffff")
        if not bg_colour or not bg_colour[0]:
            # default white
            bg_rgb = (255, 255, 255)
        else:
            bg_rgb = tuple(int(v) for v in bg_colour[0])
        # Determine canvas size
        canvas_w = cell_w * cols
        canvas_h = cell_h * rows
        # Save history before modifications
        self._save_history()
        if replace:
            # Clear layers and history for new document
            self.layers = []
            self.history = []
            self.history_index = -1
            # Set new canvas size
            self.canvas.config(width=canvas_w, height=canvas_h)
        # Create background base layer if replacing
        if replace:
            bg_img = Image.new("RGBA", (canvas_w, canvas_h), bg_rgb + (255,))
            bg_layer = Layer(bg_img, "Collage Background")
            self.layers.append(bg_layer)
        # Add each selected image as a new layer
        for idx, p in enumerate(paths):
            try:
                img = Image.open(p).convert("RGBA")
            except Exception as e:
                messagebox.showerror("Error", f"Could not open {p}: {e}")
                continue
            # Scale image to cell size preserving aspect ratio
            # Compute scale factor
            scale_x = cell_w / img.width
            scale_y = cell_h / img.height
            scale = min(scale_x, scale_y)
            new_w = int(img.width * scale)
            new_h = int(img.height * scale)
            resized = img.resize((new_w, new_h), resample=Image.LANCZOS)
            # Create a blank cell and paste resized image centered
            cell_img = Image.new("RGBA", (cell_w, cell_h), (0, 0, 0, 0))
            paste_x = (cell_w - new_w) // 2
            paste_y = (cell_h - new_h) // 2
            cell_img.paste(resized, (paste_x, paste_y), resized)
            layer_name = f"Collage {idx}" if replace else f"Collage {len(self.layers)}"
            layer = Layer(cell_img, layer_name)
            # Determine offset for cell position
            row = idx // cols
            col = idx % cols
            layer.offset = (col * cell_w, row * cell_h)
            self.layers.append(layer)
        # Set current layer to last added layer
        if self.layers:
            self.current_layer_index = len(self.layers) - 1
        # Refresh and composite
        self._refresh_layer_list()
        self._update_composite()

    def _layout_visible_layers(self) -> None:
        """Arrange all visible layers into a grid collage within the current document.

        The user specifies the number of columns and whether to scale layers.  Layers
        are repositioned (and optionally resized) to fit into a collage grid.
        """
        if not self.layers:
            return
        # Collect visible layers to arrange
        visible_layers = [layer for layer in self.layers if layer.visible]
        if not visible_layers:
            messagebox.showinfo("No Visible Layers", "There are no visible layers to layout.")
            return
        n = len(visible_layers)
        cols = simpledialog.askinteger(
            "Columns",
            "Enter number of columns (1-10)",
            initialvalue=min(3, n),
            minvalue=1,
            maxvalue=max(10, n),
        )
        if cols is None or cols <= 0:
            return
        rows = (n + cols - 1) // cols
        # Ask if scale to uniform cell size
        do_scale = messagebox.askyesno(
            "Scale Layers",
            "Scale layers to fit cells?\nYes: images scaled uniformly to cell size\nNo: images keep original size and may overflow",
        )
        # Determine cell size
        # Use max width and height among visible layers as default cell size
        max_w = max(layer.original.width for layer in visible_layers)
        max_h = max(layer.original.height for layer in visible_layers)
        # Ask optional cell width/height
        if do_scale:
            cell_w = simpledialog.askinteger(
                "Cell Width",
                "Enter width for each cell (pixels)",
                initialvalue=max_w,
                minvalue=1,
            )
            if cell_w is None:
                return
            cell_h = simpledialog.askinteger(
                "Cell Height",
                "Enter height for each cell (pixels)",
                initialvalue=max_h,
                minvalue=1,
            )
            if cell_h is None:
                return
        else:
            cell_w, cell_h = max_w, max_h
        # Compute new canvas size
        new_w = cell_w * cols
        new_h = cell_h * rows
        # Save history
        self._save_history()
        # Optionally scale each visible layer
        for layer in visible_layers:
            # Determine cell index for this layer (preserve order of visible_layers)
            idx = visible_layers.index(layer)
            r = idx // cols
            c = idx % cols
            if do_scale:
                # Scale original and mask
                w, h = layer.original.size
                scale_x = cell_w / w
                scale_y = cell_h / h
                scale = min(scale_x, scale_y)
                new_size = (int(w * scale), int(h * scale))
                resized = layer.original.resize(new_size, resample=Image.LANCZOS)
                # Resize mask accordingly
                layer.original = resized
                layer.mask = layer.mask.resize(new_size, resample=Image.LANCZOS)
                # Reset selective colour factors? Keep same
                layer.apply_adjustments()
                # Create a cell image to center
                # but easier: set offset to position so that image appears at top-left of cell; we keep original size but we center if cell bigger than image width/height
            # Set layer offset to position within collage
            offset_x = c * cell_w
            offset_y = r * cell_h
            # If not scaling, we may want to center smaller images within cell
            if do_scale:
                # After scaling, layer.original size may be smaller than cell; compute centre offset
                dw = layer.original.width
                dh = layer.original.height
                offset_x += (cell_w - dw) // 2
                offset_y += (cell_h - dh) // 2
            layer.offset = (offset_x, offset_y)
        # Optionally adjust canvas size
        self.canvas.config(width=new_w, height=new_h)
        self._refresh_layer_list()
        self._update_composite()

    # ------------------------------------------------------------------
    # Advanced collage creation
    # ------------------------------------------------------------------
    def _create_collage_advanced(self) -> None:
        """Create a customised collage from multiple files with advanced layout options.

        Users can choose a layout type (grid, horizontal, vertical, random),
        specify spacing and margins, cell sizes and whether to start a new
        document.  Images are scaled to fit within their cells and arranged
        accordingly.  Background colour is also configurable.
        """
        # Prompt for files
        filetypes = [("Image files", "*.png;*.jpg;*.jpeg;*.bmp;*.gif"), ("All files", "*.*")]
        paths = filedialog.askopenfilenames(title="Select Images for Collage", filetypes=filetypes)
        if not paths:
            return
        num_images = len(paths)
        # Ask layout type
        layout = simpledialog.askstring(
            "Collage Layout",
            "Enter layout type (grid, horizontal, vertical, random):",
            initialvalue="grid",
        )
        if not layout:
            return
        layout = layout.strip().lower()
        if layout not in ("grid", "horizontal", "vertical", "random"):
            messagebox.showinfo("Unsupported Layout", f"Layout '{layout}' is not supported.")
            return
        # Ask whether to start a new document
        replace = messagebox.askyesno(
            "New Document?",
            "Create collage in a new document?\nThis will discard current layers.",
        )
        # Ask background colour
        bg_colour = colorchooser.askcolor(title="Choose background colour for collage", initialcolor="#ffffff")
        if not bg_colour or not bg_colour[0]:
            bg_rgb = (255, 255, 255)
        else:
            bg_rgb = tuple(int(v) for v in bg_colour[0])
        # Load first image for default size
        try:
            first_img = Image.open(paths[0]).convert("RGBA")
        except Exception as e:
            messagebox.showerror("Error", f"Unable to open image: {e}")
            return
        default_w, default_h = first_img.size
        # Ask cell size
        cell_w = simpledialog.askinteger(
            "Cell Width",
            "Enter width for each cell (pixels)",
            initialvalue=default_w,
            minvalue=1,
        )
        if cell_w is None:
            return
        cell_h = simpledialog.askinteger(
            "Cell Height",
            "Enter height for each cell (pixels)",
            initialvalue=default_h,
            minvalue=1,
        )
        if cell_h is None:
            return
        # Ask for spacing and margin
        spacing = simpledialog.askinteger(
            "Spacing",
            "Enter spacing between cells (pixels)",
            initialvalue=10,
            minvalue=0,
        )
        if spacing is None:
            return
        margin = simpledialog.askinteger(
            "Margin",
            "Enter margin around collage (pixels)",
            initialvalue=20,
            minvalue=0,
        )
        if margin is None:
            return
        # Determine grid dimensions
        if layout == "grid":
            cols = simpledialog.askinteger(
                "Columns",
                "Enter number of columns",
                initialvalue=min(3, num_images),
                minvalue=1,
                maxvalue=max(10, num_images),
            )
            if not cols or cols <= 0:
                return
            rows = (num_images + cols - 1) // cols
        elif layout == "horizontal":
            cols = num_images
            rows = 1
        elif layout == "vertical":
            cols = 1
            rows = num_images
        else:
            cols = rows = None
            canvas_w = simpledialog.askinteger(
                "Canvas Width",
                "Enter width of collage canvas (pixels)",
                initialvalue=default_w * num_images,
                minvalue=1,
            )
            if canvas_w is None:
                return
            canvas_h = simpledialog.askinteger(
                "Canvas Height",
                "Enter height of collage canvas (pixels)",
                initialvalue=default_h * num_images,
                minvalue=1,
            )
            if canvas_h is None:
                return
        # Compute canvas size
        if layout == "grid":
            canvas_w = margin * 2 + cols * cell_w + (cols - 1) * spacing
            canvas_h = margin * 2 + rows * cell_h + (rows - 1) * spacing
        elif layout == "horizontal":
            canvas_w = margin * 2 + num_images * cell_w + (num_images - 1) * spacing
            canvas_h = margin * 2 + cell_h
        elif layout == "vertical":
            canvas_w = margin * 2 + cell_w
            canvas_h = margin * 2 + num_images * cell_h + (num_images - 1) * spacing
        # Save history
        self._save_history()
        if replace:
            # Clear layers and history
            self.layers = []
            self.history = []
            self.history_index = -1
        # Configure canvas size
        self.canvas.config(width=canvas_w, height=canvas_h)
        # Create background layer if replacing
        if replace:
            bg_img = Image.new("RGBA", (canvas_w, canvas_h), bg_rgb + (255,))
            self.layers.append(Layer(bg_img, "Collage Background"))
        # Add each image as a layer
        import random
        for idx, path in enumerate(paths):
            try:
                img = Image.open(path).convert("RGBA")
            except Exception as e:
                messagebox.showerror("Error", f"Could not open {path}: {e}")
                continue
            # Resize to fit cell
            scale_x = cell_w / img.width
            scale_y = cell_h / img.height
            scale = min(scale_x, scale_y)
            new_w = max(1, int(img.width * scale))
            new_h = max(1, int(img.height * scale))
            resized = img.resize((new_w, new_h), resample=Image.LANCZOS)
            # Create cell
            cell_img = Image.new("RGBA", (cell_w, cell_h), (0, 0, 0, 0))
            paste_x = (cell_w - new_w) // 2
            paste_y = (cell_h - new_h) // 2
            cell_img.paste(resized, (paste_x, paste_y), resized)
            layer_name = f"Collage {idx}" if replace else f"Collage {len(self.layers)}"
            layer = Layer(cell_img, layer_name)
            # Determine offset
            if layout == "grid":
                r = idx // cols
                c = idx % cols
                offset_x = margin + c * (cell_w + spacing)
                offset_y = margin + r * (cell_h + spacing)
            elif layout == "horizontal":
                offset_x = margin + idx * (cell_w + spacing)
                offset_y = margin
            elif layout == "vertical":
                offset_x = margin
                offset_y = margin + idx * (cell_h + spacing)
            else:
                # random placement within margins
                max_x = max(margin, canvas_w - margin - cell_w)
                max_y = max(margin, canvas_h - margin - cell_h)
                offset_x = random.randint(margin, max_x)
                offset_y = random.randint(margin, max_y)
            layer.offset = (offset_x, offset_y)
            self.layers.append(layer)
        # Set selection to last added layer
        if self.layers:
            self.current_layer_index = len(self.layers) - 1
        self._refresh_layer_list()
        self._update_composite()

    # ------------------------------------------------------------------
    # Auto balance layers for composition
    # ------------------------------------------------------------------
    def _auto_balance_layers(self) -> None:
        """Automatically adjust brightness of all visible layers for consistent exposure.

        This helper computes the average luminance of each visible layer and
        scales its brightness so that all layers tend toward a common mean.
        It's useful when combining photos with different exposures.
        """
        if not self.layers:
            return
        # Collect visible layers
        visible_layers = [layer for layer in self.layers if layer.visible]
        if not visible_layers:
            return
        # Compute mean brightness for each visible layer
        means = []
        for layer in visible_layers:
            gray = layer.original.convert("L")
            hist = gray.histogram()
            total = gray.width * gray.height
            s = 0
            for i, count in enumerate(hist):
                s += i * count
            mean_val = s / total if total > 0 else 0
            means.append(mean_val)
        # Determine target mean brightness
        target = sum(means) / len(means)
        # Save history once before adjusting
        self._save_history()
        for i, layer in enumerate(visible_layers):
            current_mean = means[i]
            if current_mean <= 0:
                factor = 1.0
            else:
                factor = target / current_mean
            # Clamp factor to [0.5, 2.0] to avoid extremes
            factor = max(0.5, min(2.0, factor))
            layer.brightness *= factor
            # Apply adjustments to update working copy
            layer.apply_adjustments()
        # Update sliders to reflect current layer's properties
        if self.current_layer_index is not None:
            curr = self.layers[self.current_layer_index]
            self.brightness_slider.set(curr.brightness)
            self.contrast_slider.set(curr.contrast)
        # Refresh composite
        self._update_composite()

    # ------------------------------------------------------------------
    # Template collage creation
    # ------------------------------------------------------------------
    def _create_template_layout(self, template: str) -> None:
        """Quickly create a collage based on a predefined template.

        Templates:
        - "2x2": 2 rows x 2 columns grid
        - "3x3": 3 rows x 3 columns grid
        - "1x3h": 1 row x 3 columns (horizontal strip)
        - "3x1v": 3 rows x 1 column (vertical strip)
        - "random": random placement in specified canvas

        When invoked, the user is prompted to select images and can customise
        cell size, spacing, margin and background colour. The layout is
        then created on a new canvas (with option to retain current layers).
        """
        # Map template identifiers to layout type and grid dimensions
        layout = "grid"
        rows = cols = None
        if template == "2x2":
            rows, cols = 2, 2
        elif template == "3x3":
            rows, cols = 3, 3
        elif template == "1x3h":
            rows, cols = 1, 3
            layout = "horizontal"
        elif template == "3x1v":
            rows, cols = 3, 1
            layout = "vertical"
        elif template == "random":
            layout = "random"
        else:
            messagebox.showinfo("Unknown Template", f"Template '{template}' is not recognised.")
            return
        # Ask for images
        filetypes = [("Image files", "*.png;*.jpg;*.jpeg;*.bmp;*.gif"), ("All files", "*.*")]
        paths = filedialog.askopenfilenames(title="Select Images for Template", filetypes=filetypes)
        if not paths:
            return
        num_images = len(paths)
        # Determine grid dims if not random
        if layout == "grid":
            # Use provided rows/cols; if more images, extend rows automatically
            if rows is None or cols is None:
                # Fallback to square grid
                cols = int(math.ceil(math.sqrt(num_images)))
                rows = int(math.ceil(num_images / cols))
            else:
                # Adjust rows if needed
                needed_rows = (num_images + cols - 1) // cols
                if needed_rows > rows:
                    rows = needed_rows
        elif layout == "horizontal":
            # 1 row, columns equal to number of images
            rows, cols = 1, num_images
        elif layout == "vertical":
            rows, cols = num_images, 1
        # Ask cell size (default from first image)
        try:
            img0 = Image.open(paths[0]).convert("RGBA")
        except Exception as e:
            messagebox.showerror("Error", f"Unable to open image: {e}")
            return
        default_w, default_h = img0.size
        cell_w = simpledialog.askinteger(
            "Cell Width",
            "Enter width for each cell (pixels)",
            initialvalue=default_w,
            minvalue=1,
        )
        if cell_w is None:
            return
        cell_h = simpledialog.askinteger(
            "Cell Height",
            "Enter height for each cell (pixels)",
            initialvalue=default_h,
            minvalue=1,
        )
        if cell_h is None:
            return
        # Ask spacing and margin with defaults
        spacing = simpledialog.askinteger(
            "Spacing",
            "Enter spacing between cells (pixels)",
            initialvalue=10,
            minvalue=0,
        )
        if spacing is None:
            return
        margin = simpledialog.askinteger(
            "Margin",
            "Enter margin around collage (pixels)",
            initialvalue=20,
            minvalue=0,
        )
        if margin is None:
            return
        # Ask background colour
        bg_colour = colorchooser.askcolor(title="Choose background colour", initialcolor="#ffffff")
        if not bg_colour or not bg_colour[0]:
            bg_rgb = (255, 255, 255)
        else:
            bg_rgb = tuple(int(v) for v in bg_colour[0])
        # Ask whether to start new doc
        replace = messagebox.askyesno(
            "New Document?",
            "Create this collage in a new document?\nThis will discard current layers.",
        )
        # Determine canvas size
        if layout == "grid":
            canvas_w = margin * 2 + cols * cell_w + (cols - 1) * spacing
            canvas_h = margin * 2 + rows * cell_h + (rows - 1) * spacing
        elif layout == "horizontal":
            canvas_w = margin * 2 + num_images * cell_w + (num_images - 1) * spacing
            canvas_h = margin * 2 + cell_h
        elif layout == "vertical":
            canvas_w = margin * 2 + cell_w
            canvas_h = margin * 2 + num_images * cell_h + (num_images - 1) * spacing
        else:  # random
            # Ask canvas size for random mosaic
            canvas_w = simpledialog.askinteger(
                "Canvas Width",
                "Enter width of the random mosaic canvas (pixels)",
                initialvalue=default_w * max(1, min(num_images, 3)),
                minvalue=1,
            )
            if canvas_w is None:
                return
            canvas_h = simpledialog.askinteger(
                "Canvas Height",
                "Enter height of the random mosaic canvas (pixels)",
                initialvalue=default_h * max(1, min(num_images, 3)),
                minvalue=1,
            )
            if canvas_h is None:
                return
        # Save history and optionally clear
        self._save_history()
        if replace:
            self.layers = []
            self.history = []
            self.history_index = -1
        # Set canvas size
        self.canvas.config(width=canvas_w, height=canvas_h)
        # Create background layer if replacing
        if replace:
            bg_img = Image.new("RGBA", (canvas_w, canvas_h), bg_rgb + (255,))
            self.layers.append(Layer(bg_img, "Template Background"))
        import random
        # Add each image
        for idx, path in enumerate(paths):
            try:
                img = Image.open(path).convert("RGBA")
            except Exception as e:
                messagebox.showerror("Error", f"Could not open {path}: {e}")
                continue
            # Resize to fit cell
            scale_x = cell_w / img.width
            scale_y = cell_h / img.height
            scale = min(scale_x, scale_y)
            new_w = max(1, int(img.width * scale))
            new_h = max(1, int(img.height * scale))
            resized = img.resize((new_w, new_h), resample=Image.LANCZOS)
            # Create cell image
            cell_img = Image.new("RGBA", (cell_w, cell_h), (0, 0, 0, 0))
            paste_x = (cell_w - new_w) // 2
            paste_y = (cell_h - new_h) // 2
            cell_img.paste(resized, (paste_x, paste_y), resized)
            layer_name = f"Template {idx}" if replace else f"Template {len(self.layers)}"
            layer = Layer(cell_img, layer_name)
            # Determine offset
            if layout == "grid":
                r = idx // cols
                c = idx % cols
                offset_x = margin + c * (cell_w + spacing)
                offset_y = margin + r * (cell_h + spacing)
            elif layout == "horizontal":
                offset_x = margin + idx * (cell_w + spacing)
                offset_y = margin
            elif layout == "vertical":
                offset_x = margin
                offset_y = margin + idx * (cell_h + spacing)
            else:  # random
                max_x = max(margin, canvas_w - margin - cell_w)
                max_y = max(margin, canvas_h - margin - cell_h)
                offset_x = random.randint(margin, max_x)
                offset_y = random.randint(margin, max_y)
            layer.offset = (offset_x, offset_y)
            self.layers.append(layer)
        # Update selection and composite
        if self.layers:
            self.current_layer_index = len(self.layers) - 1
        self._refresh_layer_list()
        self._update_composite()

    # ------------------------------------------------------------------
    # Draft management (local storage)
    # ------------------------------------------------------------------
    def _save_draft(self) -> None:
        """Save the current editing session to a draft file in the draft directory.

        The user is prompted for a name, and the current history snapshot
        (including all layers and their properties) is stored using pickle.
        """
        if not self.layers:
            messagebox.showinfo("Nothing to Save", "There is no layer to save as a draft.")
            return
        # Ask for draft name
        name = simpledialog.askstring("Save Draft", "Enter a name for this draft:")
        if not name:
            return
        # Save current history snapshot
        # Ensure the latest state is saved
        self._save_history()
        if self.history_index < 0:
            messagebox.showerror("Error", "No state available to save.")
            return
        snapshot = self.history[self.history_index]
        import pickle
        filename = os.path.join(self.draft_dir, f"{name}.pkl")
        try:
            with open(filename, "wb") as f:
                pickle.dump(snapshot, f)
            messagebox.showinfo("Draft Saved", f"Draft '{name}' saved successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save draft: {e}")

    def _load_draft(self) -> None:
        """Load a previously saved draft from the draft directory.

        Presents a file selection dialog to the user listing available drafts.
        Upon selection, the snapshot is loaded and the editor state is restored.
        """
        import pickle
        # List all draft files in the directory
        if not os.path.isdir(self.draft_dir):
            messagebox.showinfo("No Drafts", "Draft directory does not exist.")
            return
        draft_files = [f for f in os.listdir(self.draft_dir) if f.endswith(".pkl")]
        if not draft_files:
            messagebox.showinfo("No Drafts", "There are no saved drafts to load.")
            return
        # Ask user to choose a draft; use file dialog for convenience
        filepath = filedialog.askopenfilename(
            title="Load Draft",
            initialdir=self.draft_dir,
            filetypes=[("Draft files", "*.pkl")],
        )
        if not filepath:
            return
        try:
            with open(filepath, "rb") as f:
                snapshot = pickle.load(f)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load draft: {e}")
            return
        # Restore state
        self._restore_history_state(snapshot)
        # Reset history to just this snapshot
        self.history = [snapshot]
        self.history_index = 0
        messagebox.showinfo("Draft Loaded", f"Draft loaded from {os.path.basename(filepath)}.")

    def _delete_all_drafts(self) -> None:
        """Delete all saved draft files after user confirmation."""
        if not os.path.isdir(self.draft_dir):
            messagebox.showinfo("No Drafts", "There are no drafts to delete.")
            return
        confirm = messagebox.askyesno(
            "Delete All Drafts",
            "Are you sure you want to delete all saved drafts? This action cannot be undone.",
        )
        if not confirm:
            return
        deleted = 0
        for filename in os.listdir(self.draft_dir):
            path = os.path.join(self.draft_dir, filename)
            try:
                os.remove(path)
                deleted += 1
            except Exception:
                pass
        messagebox.showinfo("Drafts Deleted", f"Deleted {deleted} draft(s).")


def main():
    app = ImageEditor()
    app.mainloop()


if __name__ == "__main__":
    main()