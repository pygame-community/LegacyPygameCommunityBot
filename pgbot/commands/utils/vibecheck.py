"""
This file is a part of the source code for the PygameCommunityBot.
This project has been licensed under the MIT license.
Copyright (c) 2020-present PygameCommunityDiscord

This file defines several functions used to get the pie chart of the bot's emotions
"""

import math
import os

import pygame

from pgbot import emotion

emotions_per_row = 2
negative_emotion = {"bored": "exhausted", "happy": "sad"}
emotion_color = {
    "happy": (230, 28, 226),
    "sad": (28, 28, 230),
    "anger": (230, 36, 18),
    "bored": (230, 181, 18),
    "exhausted": (235, 127, 19),
    "confused": (19, 235, 228),
}


def generate_pie_slice(center_x, center_y, radius, start_angle, end_angle):
    p = [(center_x, center_y)]

    for angle in range(start_angle - 90, end_angle - 90):
        x = center_x + int(radius * math.cos(math.radians(angle)))
        y = center_y + int(radius * math.sin(math.radians(angle)))
        p.append((x, y))
    return p


def get_emotion_percentage(emotions, round_by=1):
    raw_emotion_percentage = {}
    for key, value in emotions.items():
        percentage = value / emotion.EMOTION_CAPS[key][1] * 100
        if percentage < 0:
            percentage = -percentage
            key = negative_emotion[key]
        raw_emotion_percentage[key] = percentage

    sum_of_emotions = sum([i for i in raw_emotion_percentage.values()])
    emotion_percentage = {
        key: round(raw_emotion / sum_of_emotions * 100, round_by)
        if round_by != -1
        else raw_emotion / sum_of_emotions * 100
        for key, raw_emotion in sorted(
            raw_emotion_percentage.items(), key=lambda item: item[1], reverse=True
        )
    }

    return emotion_percentage


def emotion_pie_chart(emotions, pie_radius):
    """
    Generates a pie chart, given emotions and pie radius
    Emotions must be in "raw form" (E.g {"happy": 34, "bored": -345, "anger": 89, "confused": 499})
    """
    font = pygame.font.Font(os.path.join("assets", "tahoma.ttf"), 30)
    font.bold = True

    image = pygame.Surface((pie_radius * 2, pie_radius * 2 + 30 * len(emotions)))
    image.fill((0, 0, 0, 0))

    emotion_percentage = get_emotion_percentage(emotions)

    emotion_pie_angle = {
        key: percentage / 100 * 360 for key, percentage in emotion_percentage.items()
    }
    start_angle = 0
    for key, angle in emotion_pie_angle.items():
        if round(angle) != 0:
            pygame.draw.polygon(
                image,
                emotion_color[key],
                generate_pie_slice(
                    pie_radius,
                    pie_radius,
                    pie_radius,
                    start_angle,
                    start_angle + round(angle),
                ),
            )
            start_angle += round(angle)

    pygame.draw.circle(
        image, (255, 255, 255), (pie_radius, pie_radius), pie_radius, width=10
    )

    i = 0
    txt_x = 0
    txt_y = pie_radius * 2
    for bot_emotion, percentage in emotion_percentage.items():
        txt = font.render(
            f"{bot_emotion.title()} - {percentage}%", True, emotion_color[bot_emotion]
        )
        txt_rect = txt.get_rect(topleft=(txt_x, txt_y))
        image.blit(txt, txt_rect)

        pygame.draw.rect(
            image,
            emotion_color[bot_emotion],
            (txt_x + pie_radius * 1.8 / emotions_per_row, txt_y, 20, 40),
        )

        if i % emotions_per_row != emotions_per_row - 1:
            txt_x += pie_radius * 2 / emotions_per_row
        else:
            txt_x = 0
            txt_y += 40
        i += 1

    return image
