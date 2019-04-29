import json
import os
from typing import List, Optional

from ..render_tools import blender_render as blender

from .crop_generator import WORK_DIR, OUTPUT_DIR, FloatingPointBox, Crop
from .image_metrics_calculator import calculate_metrics


def get_crop_with_id(id: int, crops: [List[Crop]]) -> Optional[Crop]:
    for crop in crops:
        if crop.id == id:
            return crop
    return None


def prepare_crops(
        subtask_image_box,
        resolution,
        crops_count=3,
        crops_borders=None,
):
    crops_details: List[Crop] = []
    crops_render_data = []
    if crops_borders:
        crop_id = 0
        for border in crops_borders:
            crop = Crop(
                crop_id,
                resolution,
                subtask_image_box,
                FloatingPointBox(border[0], border[1], border[2], border[3]),
            )
            crops_render_data.append(
                {
                    "id": crop.id,
                    "outfilebasename": "crop" + str(crop_id) + '_',
                    "borders_x": [crop.box.left,
                                  crop.box.right],
                    "borders_y": [crop.box.top, crop.box.bottom]
                }
            )
            crops_details.append(crop)
            crop_id += 1
    else:
        for crop_id in range(0, crops_count):
            crop = Crop(
                crop_id,
                resolution,
                subtask_image_box,
            )
            crops_render_data.append(
                {
                    "id": crop.id,
                    "outfilebasename": "crop" + str(crop_id) + '_',
                    "borders_x": [crop.box.left,
                                  crop.box.right],
                    "borders_y": [crop.box.top, crop.box.bottom]
                }
            )
            crops_details.append(crop)
    return crops_details, crops_render_data


def prepare_data_for_blender_verification(  # pylint: disable=too-many-locals, too-many-arguments
        subtask_border,
        scene_file_path,
        resolution,
        samples,
        frames,
        output_format,
        crops_count=3,
        crops_borders=None,

):
    subtask_image_box = FloatingPointBox(
        subtask_border[0],
        subtask_border[1],
        subtask_border[2],
        subtask_border[3]
    )

    (crops_details, crops_render_data) = prepare_crops(
        subtask_image_box,
        resolution,
        crops_count,
        crops_borders
    )

    params = {
        "scene_file": scene_file_path,
        "resolution": resolution,
        "use_compositing": False,
        "samples": samples,
        "frames": frames,
        "start_task": 1,
        "output_format": output_format,
        "crops": crops_render_data
    }

    return (crops_details, params)


def make_verdict(
        providers_result_images_paths,
        crops_details,
        reference_results,
):
    verdict = True

    for crop_data in reference_results:
        crop = get_crop_with_id(crop_data['crop']['id'], crops_details)

        left, top = crop.x_pixels[0], crop.y_pixels[0]
        print('borders_x: ', crop_data['crop']['borders_x'])
        print('borders_y: ', crop_data['crop']['borders_y'])
        print("left: " + str(left))
        print("top: " + str(top))

        for crop, providers_result_image_path in zip(
                crop_data['results'], providers_result_images_paths):
            crop_path = os.path.join(OUTPUT_DIR, crop)
            results_path = calculate_metrics(
                crop_path,
                providers_result_image_path,
                left, top,
                metrics_output_filename=os.path.join(
                    OUTPUT_DIR,
                    crop_data['crop']['outfilebasename'] + "metrics.txt")
            )
            print("results_path: ", results_path)
            with open(results_path, 'r') as f:
                data = json.load(f)
            if data['Label'] != "TRUE":
                verdict = False

    with open(os.path.join(OUTPUT_DIR, 'verdict.json'), 'w') as f:
        json.dump({'verdict': verdict}, f)


def verify(  # pylint: disable=too-many-arguments
        subtask_file_paths,
        subtask_border,
        scene_file_path,
        resolution,
        samples,
        frames,
        output_format,
        crops_count=3,
        crops_borders=None,
):
    """
    Function will verify image with crops rendered from given blender
    scene file.

    subtask_file_paths - path (or paths if there was more than one frame)
                         to image file, that will be compared against crops
    subtask_border - [left, top, right, bottom] float decimal values
                     representing image localization in whole blender scene
    scene_file_path - path to blender scene file
    resolution - resolution at which given subtask was rendered
                 (crop will be rendered with exactly same parameters)
    samples - samples at which given subtask was rendered
    frames - number of frames that are present in subtasks
    output_format - output format of rendered crops
    crops_count - number of randomly generated crops, (default 3)
    crops_borders - list of [left, top, right, bottom] float decimal
                    values lists, representing crops borders
                    those will be used instead of random crops, if present.
    """
    mounted_paths = dict()
    mounted_paths["WORK_DIR"] = WORK_DIR
    mounted_paths["OUTPUT_DIR"] = OUTPUT_DIR

    (crops_details,
     blender_render_parameters) = prepare_data_for_blender_verification(
        subtask_border,
        scene_file_path,
        resolution,
        samples,
        frames,
        output_format,
        crops_count,
        crops_borders
    )

    results = blender.render(blender_render_parameters, mounted_paths)

    print(results)

    make_verdict(subtask_file_paths, crops_details, results)
