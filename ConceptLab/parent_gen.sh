python -m scripts.infer --prompts="['a photo of a {}']" --output_dir outputs/parents/parent_monster/ \
 --learned_embeds_path outputs/monster/250_step_embeds.bin --samples_per_prompt=32

python -m scripts.infer --prompts="['a photo of a {}']" --output_dir outputs/parents/parent_monster2/ \
 --learned_embeds_path outputs/monster/1750_step_embeds.bin --samples_per_prompt=32

python -m scripts.infer --prompts="['a photo of a {}']" --output_dir outputs/parents/parent_building/ \
 --learned_embeds_path outputs/building/1750_step_embeds.bin --samples_per_prompt=32

python -m scripts.infer --prompts="['a photo of a {}']" --output_dir outputs/parents/parent_weapon/ \
 --learned_embeds_path outputs/weapon/250_step_embeds.bin --samples_per_prompt=32

python -m scripts.infer --prompts="['a photo of a {}']" --output_dir outputs/parents/parent_pet/ \
 --learned_embeds_path outputs/pets/1250_step_embeds.bin --samples_per_prompt=32