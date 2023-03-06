import random
from typing import List, Optional

from .modular_page import Control, ModularPage, Prompt
from .timeline import MediaSpec
from .utils import is_valid_html5_id


class GraphicMixin:
    """
    A mix-in corresponding to a graphic panel.

    Parameters
    ----------

    id_
        An identifier for the graphic, should be parsable as a valid variable name.

    frames
        List of :class:`psynet.graphic.Frame` objects.
        These frames will be displayed in sequence to the participant.

    dimensions
        A list containing two numbers, corresponding to the x and y dimensions of the graphic.
        The ratio of these numbers determines the aspect ratio of the graphic.
        They define the coordinate system according to which objects are plotted.
        However, the absolute size of the graphic is independent of the size of these numbers
        (i.e. a 200x200 graphic occupies the same size on the screen as a 100x100 graphic).

    viewport_width
        The width of the graphic display, expressed as a fraction of the browser window's width.
        The default value (0.6) means that the graphic occupies 60% of the window's width.

    loop
        Whether the graphic should loop back to the first frame once the last frame has finished.

    media
        Optional :class:`psynet.timeline.MediaSpec` object providing audio and image files to
        be used within the graphic.

    **kwargs
        Additional parameters passed to parent classes.
    """

    margin: str = "25px"
    "CSS margin property for the graphic panel."

    border_style: str = "solid"
    "CSS border-style property for the graphic panel."

    border_color: str = "#cfcfcf"
    "CSS border-color property for the graphic panel."

    border_width: str = "1px"
    "CSS border-width property for the graphic panel."

    def __init__(
        self,
        id_: str,
        frames: "List[Frame]",
        dimensions: List,
        viewport_width: float = 0.6,
        loop: bool = False,
        media: Optional[MediaSpec] = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.id = id_
        self.frames = frames
        self.dimensions = dimensions
        self.viewport_width = viewport_width
        self.loop = loop
        self._media = media
        self.validate_id(id_)
        self.validate_frames(frames)
        self.validate_media(media)

    def validate_media(self, media):
        if not (media is None or isinstance(media, MediaSpec)):
            raise ValueError(
                "media must either be None or an instance of class MediaSpec"
            )

        if media is None:
            media = MediaSpec()

        media_ids = media.ids

        for frame in self.frames:
            if frame.audio_id is not None:
                if frame.audio_id not in media_ids["audio"]:
                    raise ValueError(
                        f"audio '{frame.audio_id}' was missing from the media collection"
                    )

            for obj in frame.objects:
                if isinstance(obj, Image):
                    if obj.media_id not in media_ids["image"]:
                        raise ValueError(
                            f"image '{obj.media_id}' was missing from the media collection"
                        )

    def validate_id(self, id_):
        if not isinstance(id_, str):
            raise ValueError("id_ must be a string")
        if not is_valid_html5_id(id_):
            raise ValueError("id_ must be a valid HTML5 id")

    def validate_frames(self, frames):
        for f in frames:
            assert isinstance(f, Frame)
        self.validate_object_ids(frames)

    def validate_object_ids(self, frames):
        persistent_objects = set()
        for frame_id, frame in enumerate(frames):
            frame_objects = set()
            for o in frame.objects:
                if o.id in frame_objects:
                    raise ValueError(
                        f"in Graphic {self.id}, Frame {frame_id}, duplicate object ID '{o.id}'"
                    )
                if o.id in persistent_objects:
                    raise ValueError(
                        f"in Graphic {self.id}, Frame {frame_id}, tried to override persistent object '{o.id}'"
                    )
                frame_objects.add(o.id)
                if o.persist:
                    persistent_objects.add(o.id)
        return True

    @property
    def media(self):
        if self._media is None:
            return MediaSpec()
        return self._media

    @property
    def metadata(self):
        return {
            **super().metadata,
            "dimensions": self.dimensions,
            "viewport_width": self.viewport_width,
            "loop": self.loop,
            "n_frames": len(self.frames),
        }


class Frame:
    """
    A :class:`psynet.graphic.Frame` defines an image to show to the participant.

    Parameters
    ----------

    objects
        A list of :class:`psynet.graphic.Object` objects to include in the frame.

    duration
        The duration of the frame, in seconds. If ``None``, then the frame lasts forever.

    audio_id
        An optional ID for an audio file to play when the frame starts. This audio file must be provided in
        the ``media`` slot of the parent :class:`psynet.graphic.GraphicMixin`.

    activate_control_response
        If ``True``, then activate responses for the page's :class:`psynet.modular_page.Control` object
        once this frame is reached.

    activate_control_submit
        If ``True``, then enable response submission for the page's :class:`psynet.modular_page.Control` object
        once this frame is reached.
    """

    def __init__(
        self,
        objects: "List[GraphicObject]",
        duration: Optional[float] = None,
        audio_id: Optional[str] = None,
        activate_control_response: bool = False,
        activate_control_submit: bool = False,
    ):
        assert (duration is None) or (duration >= 0)
        self.objects = objects
        self.audio_id = audio_id
        self.duration = duration
        self.activate_control_response = activate_control_response
        self.activate_control_submit = activate_control_submit


class Animation:
    """
    An :class:`psynet.graphic.Animation` can be added to an :class:`psynet.graphic.Object` to provide motion.

    Parameters
    ----------

    final_attributes
        The final set of attributes that the object should attain by the end of the animation.
        Only animated attributes need to be mentioned.
        For example, to say that the object should reach an x position of 60 by the end of the animation,
        we write ``final_attributes={"x": 60}``.
        See https://dmitrybaranovskiy.github.io/raphael/reference.html#Element.attr and https://www.w3.org/TR/SVG/
        for available attributes.
        Note that the x and y coordinates for circles and ellipses are called ``cx`` and ``cy``.

    duration
        The time that the animation should take to complete, in seconds.

    easing
        Determines the dynamics of the transition between initial and final attributes.
        Permitted values are ``"linear"``, ``"ease-in"``, ``"ease-out"``, ``"ease-in-out"``,
        ``"back-in"``, ``"back-out"``, ``"elastic"``, and ``"bounce"``.
    """

    def __init__(self, final_attributes: dict, duration: float, easing: str = "linear"):
        self.final_attributes = final_attributes
        self.duration = duration
        self.easing = easing


class GraphicObject:
    """
    An object that is displayed as part of a :class:`psynet.graphic.Frame`.

    Parameters
    ----------

    id_
        A unique identifier for the object. This should be parsable as a valid variable name.

    click_to_answer
        Whether clicking on the object constitutes a valid answer, thereby advancing to the next page.

    persist
        Whether the object should persist into successive frames.
        In this case, the object must not share an ID with any objects in these successive frames.

    attributes
        A collection of attributes to give the object.
        See https://dmitrybaranovskiy.github.io/raphael/reference.html#Element.attr for valid attributes,
        and https://www.w3.org/TR/SVG/ for further details.
        For example, one might write ``{"fill": "red", "opacity" = 0.5}``.

    animations
        A list of :class:`psynet.graphic.Animation` objects .

    loop_animations
        If ``True``, then the object's animations will be looped back to the beginning once they finish.
    """

    def __init__(
        self,
        id_: str,
        click_to_answer: bool = False,
        persist: bool = False,
        attributes: Optional[dict] = None,
        animations: Optional[List] = None,
        loop_animations: bool = False,
    ):
        self.validate_id(id_)
        self.id = id_
        self.click_to_answer = click_to_answer
        self.persist = persist
        self.attributes = attributes
        self.loop_animations = loop_animations

        self.animations = None
        self.animations_js = None
        self.register_animations(animations)

    def register_animations(self, animations):
        if animations is None:
            self.animations = []
        elif isinstance(animations, Animation):
            self.animations = [animations]
        elif isinstance(animations, list):
            self.animations = animations
        else:
            raise ValueError(
                "animations must be None, or an object of class Animation, or a list of Animations"
            )

        self.animations_js = [
            {
                "index": index,
                "finalAttributes": animation.final_attributes,
                "duration": animation.duration,
                "easing": animation.easing,
            }
            for index, animation in enumerate(self.animations)
        ]

    def validate_id(self, id_):
        if not isinstance(id_, str):
            raise ValueError("id_ must be a string")
        if not is_valid_html5_id(id_):
            raise ValueError("id_ must be a valid HTML5 id")

    @property
    def js_init(self):
        return []

    @property
    def js_edit(self):
        return []


class Text(GraphicObject):
    """
    A text object.

    Parameters
    ----------

    id_
        A unique identifier for the object.

    text
        Text to display.

    x
        x coordinate.

    y
        y coordinate.

    **kwargs
        Additional parameters passed to :class:`~psynet.graphic.GraphicObject`.
    """

    def __init__(self, id_: str, text: str, x: int, y: int, **kwargs):
        super().__init__(id_, **kwargs)
        self.text = text
        self.x = round(x)
        self.y = round(y)

    @property
    def js_init(self):
        escaped_text = self.text.replace("'", "\\'")
        return [
            *super().js_init,
            f"this.raphael = paper.text({self.x}, {self.y}, '{escaped_text}');",
        ]


class Image(GraphicObject):
    """
    An image object.

    Parameters
    ----------

    id_
        A unique identifier for the object.

    media_id
        The ID for the media source, which will be looked up in the graphic's `:class:`psynet.timeline.MediaSpec`
        object.

    x
        x coordinate.

    y
        y coordinate.

    width
        Width of the drawn image.

    height
        Height of the drawn image. If ``None``, the height is set automatically with reference to ``width``.

    anchor_x
        Determines the x-alignment of the image. A value of 0.5 (default) means that the image is center-aligned.
        This alignment is achieved using the ``transform`` attribute of the image,
        bear this in mind when overriding this attribute.

    anchor_y
        Determines the y-alignment of the image. A value of 0.5 (default) means that the image is center-aligned.
        This alignment is achieved using the ``transform`` attribute of the image,
        bear this in mind when overriding this attribute.

    **kwargs
        Additional parameters passed to :class:`~psynet.graphic.GraphicObject`.
    """

    def __init__(
        self,
        id_: str,
        media_id: str,
        x: int,
        y: int,
        width: int,
        height: Optional[int] = None,
        anchor_x: float = 0.5,  # 0 means align to the left side; 1 means align to the right side
        anchor_y: float = 0.5,  # 0 means align to the top side; 1 means align to the bottom side
        **kwargs,
    ):
        super().__init__(id_, **kwargs)
        self.media_id = media_id
        self.x = round(x)
        self.y = round(y)
        self.width = round(width)
        self.anchor_x = anchor_x
        self.anchor_y = anchor_y

        if height is None:
            self.height = None
        else:
            self.height = round(height)

    @property
    def js_init(self):
        if self.height is None:
            height_js = f"Math.round({self.width} / psynet.image['{self.media_id}'].aspectRatio)"
        else:
            height_js = self.height

        return [
            *super().js_init,
            f"this.raphael = paper.image(psynet.image['{self.media_id}'].url, {self.x}, {self.y}, {self.width}, {height_js});",
        ]

    @property
    def js_edit(self):
        return [
            *super().js_edit,
            f"""
            {{
                let width = this.raphael.attr('width');
                let height = this.raphael.attr('height');
                this.x_offset = - Math.round(width * {self.anchor_x});
                this.y_offset = - Math.round(height * {self.anchor_y});
                this.raphael.transform('t' + this.x_offset + ',' + this.y_offset);
            }}
            """,
        ]


class Path(GraphicObject):
    """
    A path object. Paths provide the most flexible way to draw arbitrary vector graphics.

    Parameters
    ----------

    id_
        A unique identifier for the object.

    path_string
        The object's path string. This should be in SVG format,
        see https://dmitrybaranovskiy.github.io/raphael/reference.html#Paper.path
        and https://www.w3.org/TR/SVG/paths.html#PathData for information.

    **kwargs
        Additional parameters passed to :class:`~psynet.graphic.GraphicObject`.
    """

    def __init__(self, id_: str, path_string: str, **kwargs):
        super().__init__(id_, **kwargs)
        self.path_string = path_string

    @property
    def js_init(self) -> str:
        return [*super().js_init, f"this.raphael = paper.path('{self.path_string}');"]


class Circle(GraphicObject):
    """
    A circle object.

    Parameters
    ----------

    id_
        A unique identifier for the object.

    x
        x coordinate.

    y
        y coordinate.

    radius
        The circle's radius.

    **kwargs
        Additional parameters passed to :class:`~psynet.graphic.GraphicObject`.
    """

    def __init__(self, id_: str, x: int, y: int, radius: int, **kwargs):
        super().__init__(id_, **kwargs)
        self.x = round(x)
        self.y = round(y)
        self.radius = round(radius)

    @property
    def js_init(self) -> str:
        return [
            *super().js_init,
            f"this.raphael = paper.circle({self.x}, {self.y}, {self.radius});",
        ]


class Ellipse(GraphicObject):
    """
    An ellipse object.
    Note that for a rotated ellipse you should use the ``transform`` attribute.

    Parameters
    ----------

    id_
        A unique identifier for the object.

    x
        x coordinate.

    y
        y coordinate.

    radius_x
        The ellipse's x radius.

    radius_y
        The ellipses's y radius.

    **kwargs
        Additional parameters passed to :class:`~psynet.graphic.GraphicObject`.
    """

    def __init__(
        self, id_: str, x: int, y: int, radius_x: int, radius_y: int, **kwargs
    ):
        super().__init__(id_, **kwargs)
        self.x = round(x)
        self.y = round(y)
        self.radius_x = round(radius_x)
        self.radius_y = round(radius_y)

    @property
    def js_init(self):
        return [
            *super().js_init,
            f"this.raphael = paper.ellipse({self.x}, {self.y}, {self.radius_x}, {self.radius_y});",
        ]


class Rectangle(GraphicObject):
    """
    A rectangle object.

    Parameters
    ----------

    id_
        A unique identifier for the object.

    x
        x coordinate.

    y
        y coordinate.

    width
        Width.

    height
        Height.

    corner_radius
        Radius of the rounded corners, defaults to zero (no rounding).

    **kwargs
        Additional parameters passed to :class:`~psynet.graphic.GraphicObject`.
    """

    def __init__(
        self,
        id_: str,
        x: int,
        y: int,
        width: int,
        height: int,
        corner_radius: int = 0,
        **kwargs,
    ):
        super().__init__(id_, **kwargs)
        self.x = round(x)
        self.y = round(y)
        self.width = round(width)
        self.height = round(height)
        self.corner_radius = round(corner_radius)

    @property
    def js_init(self):
        return [
            *super().js_init,
            f"this.raphael = paper.rect({self.x}, {self.y}, {self.width}, {self.height}, {self.corner_radius});",
        ]


class GraphicPrompt(GraphicMixin, Prompt):
    """
    A graphic prompt for use in :class:`psynet.modular_page.ModularPage`.

    Parameters
    ----------

    prevent_control_response
        If ``True``, the response interface in the :class:`psynet.modular_page.Control` object is not activated
        until explicitly instructed by one of the :class:`psynet.graphic.Frame` objects.

    prevent_control_submit
        If ``True``, participants are not allowed to submit responses
        until explicitly instructed by one of the :class:`psynet.graphic.Frame` objects.

    **kwargs
        Parameters passed to :class:`~psynet.graphic.GraphicMixin` and :class:`~psynet.modular_page.Prompt`.
    """

    macro = "graphic"

    def __init__(
        self,
        *,
        prevent_control_response: bool = False,
        prevent_control_submit: bool = False,
        **kwargs,
    ):
        super().__init__(id_="prompt", **kwargs)
        self.prevent_control_response = prevent_control_response
        self.prevent_control_submit = prevent_control_submit
        self.validate()

    @property
    def metadata(self):
        return super().metadata

    def validate(self):
        response_activated, submit_activated = (False, False)
        for frame in self.frames:
            if frame.activate_control_response:
                response_activated = True
            if frame.activate_control_submit:
                submit_activated = True
        if self.prevent_control_response and not response_activated:
            raise ValueError(
                "if prevent_control_response == True, then at least one frame must have activate_control_response == True"
            )
        if self.prevent_control_submit and not submit_activated:
            raise ValueError(
                "if prevent_control_submit == True, then at least one frame must have activate_control_submit == True"
            )
        return True

    def update_events(self, events):
        if self.prevent_control_response:
            events["responseEnable"].add_trigger("graphicPromptEnableResponse")
        if self.prevent_control_submit:
            events["submitEnable"].add_trigger("graphicPromptEnableSubmit")


class GraphicControl(GraphicMixin, Control):
    """
    A graphic control for use in :class:`psynet.modular_page.ModularPage`.

    Parameters
    ----------

    auto_advance_after : float
        If not ``None``, a time in seconds after which the page will automatically advance to the next page.

    **kwargs
        Parameters passed to :class:`~psynet.graphic.GraphicMixin` and :class:`~psynet.modular_page.Control`.
    """

    macro = "graphic"

    def __init__(self, auto_advance_after: Optional[float] = None, **kwargs):
        super().__init__(id_="control", **kwargs)
        self.auto_advance_after = auto_advance_after

    @property
    def metadata(self):
        return super().metadata

    def visualize_response(self, answer, response, trial):
        raise NotImplementedError

    def get_bot_response(self, experiment, bot, page, prompt):
        if self.auto_advance_after is not None:
            return None
        else:
            clickable_objects = [
                obj
                for frame in self.frames
                for obj in frame.objects
                if obj.click_to_answer
            ]
            obj = random.choice(clickable_objects)
            try:
                coord = [obj.x, obj.y]
            except AttributeError:
                coord = [random.randint(0, span) for span in self.dimensions]
            return {"clicked_object": obj.id, "click_coordinates": coord}

        # html = (
        #         super().visualize_response(answer, response, trial) +
        #         "\n" +
        #         tags.div(
        #             tags.p(f"Answer = {answer}"),
        #             tags.video(
        #                 tags.source(src=self.url),
        #                 id="visualize-video-slider",
        #                 controls=True,
        #                 style="max-width: 400px;"
        #             )
        #         ).render()
        # )
        # return html


class GraphicPage(ModularPage):
    """
    A page that contains a single graphic.

    Parameters
    ----------

    label
        A label for the page.

    time_estimate
        A time estimate for the page (seconds).

    **kwargs
        Parameters passed to :class:`~psynet.graphic.GraphicControl`.
    """

    def __init__(self, label, *, time_estimate, **kwargs):
        super().__init__(
            label,
            Prompt(),
            GraphicControl(**kwargs),
            time_estimate=time_estimate,
        )
