import math
import os

import pygame

from .common import CLOCK_TIMEZONES


def generate_arrow_points(position, arrow_vector, thickness=5.0, size_multiplier=1.0, arrow_head_width_mul=0.75, tip_to_base_ratio=2.0 / 3.0):
    """
    Flexible function for calculating the coordinates
    for an arrow polygon defined by a position and direction
    vector. The coordinate points for the arrow polygon
    are calculated in a clockwise order,
    but returned in reverse.
    Returns a tuple containing the 2d coordinates of an arrow polygon.
    """

    thickness *= size_multiplier
    px, py = position

    arr_vec = (
        arrow_vector[0] * size_multiplier,
        arrow_vector[1] * size_multiplier
    )  # scale up the original arrow vector describing the arrow's direction

    vec_length = (arr_vec[0] ** 2 + arr_vec[1] ** 2) ** 0.5
    if not vec_length:
        return ((0, 0), ) * 7

    avp_norm = (
        -arr_vec[1] / vec_length,
        arr_vec[0] / vec_length
    )  # normalize the perpendicular arrow vector

    arrow_head_width = thickness * arrow_head_width_mul
    # multiply the arrow body width by the arrow head thickness multiplier

    avp_scaled = (
        avp_norm[0] * arrow_head_width,
        avp_norm[1] * arrow_head_width
    )  # scale up the normalized perpendicular arrow vector

    point0 = (
        avp_norm[0] * thickness,
        avp_norm[1] * thickness
    )

    point1 = (
        point0[0] + arr_vec[0] * tip_to_base_ratio,
        point0[1] + arr_vec[1] * tip_to_base_ratio
    )

    point2 = (
        point1[0] + avp_scaled[0],
        point1[1] + avp_scaled[1]
    )

    point3 = arr_vec  # tip of the arrow
    mulp4 = -(thickness * 2.0 + arrow_head_width * 2.0)
    # multiplier to mirror the normalized perpendicular arrow vector

    point4 = (
        point2[0] + avp_norm[0] * mulp4,
        point2[1] + avp_norm[1] * mulp4
    )

    point5 = (
        point4[0] + avp_scaled[0],
        point4[1] + avp_scaled[1]
    )

    point6 = (
        point5[0] + ((-arr_vec[0]) * tip_to_base_ratio),
        point5[1] + ((-arr_vec[1]) * tip_to_base_ratio)
    )

    return (
        (int(point6[0] + px), int(point6[1] + py)),
        (int(point5[0] + px), int(point5[1] + py)),
        (int(point4[0] + px), int(point4[1] + py)),
        (int(point3[0] + px), int(point3[1] + py)),
        (int(point2[0] + px), int(point2[1] + py)),
        (int(point1[0] + px), int(point1[1] + py)),
        (int(point0[0] + px), int(point0[1] + py))
    )


def user_clock(t):
    """
    Generate a 24 hour clock for special server roles
    """
    font_size = 60
    names_per_column = 5
    image_height = 1280 + font_size * names_per_column
    image = pygame.Surface((1280, image_height)).convert_alpha()
    font = pygame.font.Font(os.path.join(
        "assets", "tahoma.ttf"), font_size - 10)
    font.bold = True

    image.fill((0, 0, 0, 0))
    pygame.draw.circle(image, (255, 255, 146), (640, 640), 600,
                       draw_top_left=True, draw_top_right=True)
    pygame.draw.circle(image, (0, 32, 96), (640, 640), 600,
                       draw_bottom_left=True, draw_bottom_right=True)

    pygame.draw.circle(image, (0, 0, 0), (640, 640), 620, 32)
    time_6 = font.render("06:00", True, (0, 32, 96))
    time_12 = font.render("12:00", True, (0, 32, 96))
    time_18 = font.render("18:00", True, (0, 32, 96))
    time_0 = font.render("00:00", True, (255, 255, 146))

    actual_times = [(60, 580), (565, 60), (1060, 580), (565, 1160)]

    for time, actual_time in zip([time_6, time_12, time_18, time_0], actual_times):
        image.blit(time, actual_time)

    tx = ty = 0
    for offset, name, color in CLOCK_TIMEZONES:
        angle = (t + offset) % 86400 / 86400 * 360 + 180
        s, c = math.sin(math.radians(angle)), math.cos(math.radians(angle))

        pygame.draw.polygon(
            image, color,
            generate_arrow_points(
                (640, 640), (s * 560, -c * 560),
                thickness=5, arrow_head_width_mul=2,
                tip_to_base_ratio=0.1
            )
        )

        pygame.draw.rect(image, color, (600 + tx, 1280 + ty, 20, font_size))

        time_h = int((t + offset) // 3600 % 24)
        time_m = int((t + offset) // 60 % 60)
        text_to_render = f"{name} - {str(time_h).zfill(2)}:{str(time_m).zfill(2)}"

        text = font.render(text_to_render, True, color)
        text_rect = text.get_rect(midleft=(tx, 1280 + ty + font_size / 2))
        image.blit(text, text_rect)

        ty += font_size
        if 1280 + ty + font_size > image_height:
            ty = 0
            tx += 640

    pygame.draw.circle(image, (0, 0, 0), (640, 640), 64)

    return image
