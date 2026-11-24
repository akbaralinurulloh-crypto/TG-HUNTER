from itertools import count
from types import SimpleNamespace as NS

import pytest
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter

from app.pipeline.publisher import CAPTION_LIMIT, AiogramPublisher, MediaItem, PostPlan, build_plan, message_link, split_text

P = lambda n="a.jpg": MediaItem(__import__("pathlib").Path("/tmp/" + n), "photo")
V = lambda n="a.mp4": MediaItem(__import__("pathlib").Path("/tmp/" + n), "video")


class FakeBot:
    def __init__(self, fail_first=()):
        self.ids = count(100)
        self.calls, self.fail = [], list(fail_first)

    def _maybe_fail(self):
        if self.fail:
            raise self.fail.pop(0)

    async def send_message(self, chat_id, text, **kw):
        self._maybe_fail()
        self.calls.append(("text", chat_id, text))
        return NS(message_id=next(self.ids))

    async def send_photo(self, chat_id, photo, caption=None, **kw):
        self._maybe_fail()
        self.calls.append(("photo", chat_id, caption))
        return NS(message_id=next(self.ids))

    async def send_video(self, chat_id, video, caption=None, supports_streaming=False, **kw):
        self._maybe_fail()
        self.calls.append(("video", chat_id, caption))
        return NS(message_id=next(self.ids))

    async def send_media_group(self, chat_id, media):
        self._maybe_fail()
        self.calls.append(("group", chat_id, [(type(m).__name__, m.caption) for m in media]))
        return [NS(message_id=next(self.ids)) for _ in media]


async def nosleep(_):
    pass


def pub(bot, **kw):
    return AiogramPublisher(bot, sleep=nosleep, **kw)


def test_plan_combines_text_and_caption_when_fits():
    plan = build_plan("Asl matn", "Izoh.", [P()])
    assert plan.caption == "Asl matn\n\nIzoh." and plan.text == ""


def test_plan_attaches_instagram_url():
    url = "https://www.instagram.com/muhtasham_travel/"
    expected = f'<a href="{url}">Instagram</a>'

    plan1 = build_plan("Matn", "Izoh.", [P()], instagram_url=url)
    assert expected in plan1.caption
    assert plan1.caption.endswith(expected)
    assert "+998 88 832 77 00" in plan1.caption
    assert "@Muhtashamadmin" not in plan1.caption
    assert "https://t.me/muhtashamtraveluzz" in plan1.caption
    assert "YouTube" not in plan1.caption
    assert "Facebook" not in plan1.caption

    plan2 = build_plan("", "Faqat izoh.\n📩 @Muhtashamadmin", [P()], instagram_url=url)
    assert expected in plan2.caption
    assert "+998 88 832 77 00" in plan2.caption
    assert "@Muhtashamadmin" not in plan2.caption

    plan3 = build_plan("Aloqa: 88 832 77 00\nInstagram", "Izoh", [P()], instagram_url=url)
    assert expected in plan3.caption and plan3.caption.count("Instagram</a>") == 1

    plan4 = build_plan("Bizning sahifamiz\nИнстаграм: https://www.instagram.com/muhtasham_travel/", "Izoh", [P()], instagram_url=url)
    assert expected in plan4.caption
    assert "https://www.instagram.com" not in plan4.caption.replace(f'href="{url}"', "")

    plan5 = build_plan("Kuzatib boring: https://instagram.com/muhtasham_travel/", "", [P()], instagram_url=url)
    assert expected in plan5.caption


def test_plan_moves_long_text_out_of_caption():
    plan = build_plan("x" * 1200, "Qisqa izoh.", [P()])
    assert plan.caption == "Qisqa izoh." and plan.text == "x" * 1200 and len(plan.caption) <= CAPTION_LIMIT


def test_plan_text_only_and_media_without_text():
    assert build_plan("Matn", "", []).text == "Matn"
    assert build_plan("", "Izoh", [P()]).caption == "Izoh"


def test_plan_never_exceeds_caption_limit():
    assert len(build_plan("a" * 2000, "b" * 3000, [P()]).caption) <= CAPTION_LIMIT


def test_split_text_respects_limit_and_newlines():
    text = ("satr\n" * 2000).strip()
    parts = split_text(text, 4096)
    assert all(len(p) <= 4096 for p in parts) and "\n".join(parts).replace("\n", "") == text.replace("\n", "")


async def test_text_post():
    bot = FakeBot()
    ids = await pub(bot).publish("@kanal", PostPlan([], text="Salom"))
    assert ids == [100] and bot.calls == [("text", "@kanal", "Salom")]


async def test_single_photo_and_video_with_caption():
    bot = FakeBot()
    await pub(bot).publish("@k", PostPlan([P()], caption="Izoh"))
    await pub(bot).publish("@k", PostPlan([V()], caption="Izoh"))
    assert [c[0] for c in bot.calls] == ["photo", "video"] and bot.calls[0][2] == "Izoh"


async def test_album_posts_as_album_with_caption_on_first_only():
    bot = FakeBot()
    ids = await pub(bot).publish("@k", PostPlan([P("1.jpg"), V("2.mp4"), P("3.jpg")], caption="Izoh"))
    assert len(ids) == 3
    kind, _, group = bot.calls[0]
    assert kind == "group" and group == [("InputMediaPhoto", "Izoh"), ("InputMediaVideo", None), ("InputMediaPhoto", None)]


async def test_overflow_text_sent_as_separate_message():
    bot = FakeBot()
    ids = await pub(bot).publish("@k", PostPlan([P()], caption="Izoh", text="Uzun asl matn"))
    assert [c[0] for c in bot.calls] == ["photo", "text"] and len(ids) == 2


async def test_flood_wait_is_respected_then_succeeds():
    slept = []

    async def sleep(s):
        slept.append(s)

    bot = FakeBot([TelegramRetryAfter(method=None, message="flood", retry_after=7)])
    ids = await AiogramPublisher(bot, sleep=sleep).publish("@k", PostPlan([], text="x"))
    assert ids == [100] and slept == [8]


async def test_network_error_retried_and_gives_up():
    bot = FakeBot([TelegramNetworkError(method=None, message="down")] * 2)
    assert await pub(bot).publish("@k", PostPlan([], text="x")) == [100]
    bot = FakeBot([TelegramNetworkError(method=None, message="down")] * 10)
    with pytest.raises(TelegramNetworkError):
        await pub(bot, max_retries=2).publish("@k", PostPlan([], text="x"))


def test_message_links():
    assert message_link("@kanal", 5) == "https://t.me/kanal/5"
    assert message_link("-1001234567890", 5) == "https://t.me/c/1234567890/5"
