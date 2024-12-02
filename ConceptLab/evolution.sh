#!/bin/bash

mkdir ./outputs/evolved/evolve_building_weapon/
python -m scripts.train_evolution \
 --parents_images_dirs="['./outputs/parents/parent_building/','./outputs/parents/parent_weapon/']" \
 --initializer_token concept --output_dir ./outputs/evolved/evolve_building_weapon/ --mix_weights="[0.55,0.45]"

mkdir ./outputs/evolved/evolve_building_pet/
python -m scripts.train_evolution \
 --parents_images_dirs="['./outputs/parents/parent_building/','./outputs/parents/parent_pet/']" \
 --initializer_token concept --output_dir ./outputs/evolved/evolve_building_pet/ --mix_weights="[0.6,0.4]"

mkdir ./outputs/evolved/evolve_pet_monster/
python -m scripts.train_evolution \
 --parents_images_dirs="['./outputs/parents/parent_pet/','./outputs/parents/parent_monster/']" \
 --initializer_token concept --output_dir ./outputs/evolved/evolve_pet_monster/ --mix_weights="[0.57,0.43]"

mkdir ./outputs/evolved/evolve_pet_monster2/
python -m scripts.train_evolution \
 --parents_images_dirs="['./outputs/parents/parent_pet/','./outputs/parents/parent_monster2/']" \
 --initializer_token concept --output_dir ./outputs/evolved/evolve_pet_monster2/ --mix_weights="[0.58,0.42]"

mkdir ./outputs/evolved/evolve_animal_monster/
python -m scripts.train_evolution \
 --parents_images_dirs="['./outputs/parents/parent_animal2/','./outputs/parents/parent_monster/']" \
 --initializer_token concept --output_dir ./outputs/evolved/evolve_animal_monster2/ --mix_weights="[0.58,0.42]"

mkdir ./outputs/evolved/evolve_weapon_monster/
python -m scripts.train_evolution \
 --parents_images_dirs="['./outputs/parents/parent_weapon/','./outputs/parents/parent_monster2/']" \
 --initializer_token concept --output_dir ./outputs/evolved/evolve_pet_monster/ --mix_weights="[0.6,0.4]"

mkdir ./outputs/evolved/evolve_monster_weapon/
python -m scripts.train_evolution \
 --parents_images_dirs="['./outputs/parents/parent_monster2/','./outputs/parents/parent_weapon/']" \
 --initializer_token concept --output_dir ./outputs/evolved/evolve_monster_weapon/ --mix_weights="[0.6,0.4]"

mkdir ./outputs/evolved/evolve_human_monster/
python -m scripts.train_evolution \
 --parents_images_dirs="['./outputs/parents/parent_human/','./outputs/parents/parent_monster/']" \
 --initializer_token concept --output_dir ./outputs/evolved/evolve_human_monster/ --mix_weights="[0.55,0.45]"

mkdir ./outputs/evolved/evolve_human_vehicle/
python -m scripts.train_evolution \
 --parents_images_dirs="['./outputs/parents/parent_human/','./outputs/parents/parent_vehicle3/']" \
 --initializer_token concept --output_dir ./outputs/evolved/evolve_human_vehicle/ --mix_weights="[0.55,0.45]"