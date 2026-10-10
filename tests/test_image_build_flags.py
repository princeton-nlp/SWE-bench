"""force_rebuild / nocache plumbing in the image builder."""

import logging
from unittest.mock import MagicMock, patch

import docker.errors

from swebench.image_builder.docker_build import (
    build_instance_image,
    build_instance_images,
)
from swebench.image_builder.image_spec import ImageSpec

NOCACHE_ARG = 3  # position of nocache in a build_instance_image payload tuple


def make_spec():
    return ImageSpec(
        instance_id="owner__repo-1", dockerfile="FROM scratch\n", namespace=None
    )


def test_existing_image_is_not_rebuilt():
    client = MagicMock()
    client.images.get.return_value = MagicMock()

    with patch("swebench.image_builder.docker_build.build_image") as build_image:
        build_instance_image(make_spec(), client, logging.getLogger("test"), False)

    build_image.assert_not_called()


def test_missing_image_is_built():
    client = MagicMock()
    client.images.get.side_effect = docker.errors.ImageNotFound("nope")

    with patch("swebench.image_builder.docker_build.build_image") as build_image:
        build_instance_image(make_spec(), client, logging.getLogger("test"), False)

    build_image.assert_called_once()


def test_nocache_implies_force_rebuild():
    with (
        patch("swebench.image_builder.docker_build.remove_image") as remove_image,
        patch("swebench.image_builder.docker_build.build_instance_image") as build,
    ):
        build_instance_images(
            client=MagicMock(), image_specs=[make_spec()], nocache=True
        )

    remove_image.assert_called_once()
    assert build.call_args.args[NOCACHE_ARG] is True


def test_force_rebuild_keeps_the_layer_cache():
    with (
        patch("swebench.image_builder.docker_build.remove_image") as remove_image,
        patch("swebench.image_builder.docker_build.build_instance_image") as build,
    ):
        build_instance_images(
            client=MagicMock(), image_specs=[make_spec()], force_rebuild=True
        )

    remove_image.assert_called_once()
    assert build.call_args.args[NOCACHE_ARG] is False


def test_default_build_removes_nothing():
    with (
        patch("swebench.image_builder.docker_build.remove_image") as remove_image,
        patch("swebench.image_builder.docker_build.build_instance_image"),
    ):
        build_instance_images(client=MagicMock(), image_specs=[make_spec()])

    remove_image.assert_not_called()
