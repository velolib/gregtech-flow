# Standard libraries
import math
from bisect import bisect_right

# Internal libraries
from gregtech.flow.data.basicTypes import Ingredient, IngredientCollection


def require(recipe, requirements):
    # requirements should be a list of [key, type, reason]
    for req in requirements:
        key, req_type, reason = req
        pass_conditions = [key in vars(recipe), isinstance(getattr(recipe, key, None), req_type)]
        if not all(pass_conditions):
            raise RuntimeError(
                f'Improper config! "{recipe.machine}" requires key "{key}" - it is used for {reason}.')


class OverclockHandler:

    def __init__(self, parent_context):
        self.parent_context = parent_context
        self.ignore_underclock = False  # Whether to throw an error or actually underclock if
        # USER_VOLTAGE < EUT

        self.overclock_data = self.parent_context.data['overclock_data']

        self.voltages = self.overclock_data['voltage_data']['tiers']
        self.voltage_cutoffs = [32 * pow(4, x) + 1 for x in range(len(self.voltages))]

    def modify_gtplusplus(self, recipe):
        if recipe.machine not in self.overclock_data['gtpp_stats']:
            raise RuntimeError(
                'Missing OC data for GT++ multi - add to gtnhClasses/overclocks.py:gtpp_stats')

        # Get per-machine boosts
        speed_boost, eu_discount, parallels_per_tier = self.overclock_data['gtpp_stats'][recipe.machine]
        speed_boost = 1 / (speed_boost + 1)

        # Calculate base parallel count and clip time to 1 tick
        available_eut = self.voltage_cutoffs[self.voltages.index(recipe.user_voltage)]
        max_parallels = (self.voltages.index(recipe.user_voltage) + 1) * parallels_per_tier
        new_recipe_time = max(recipe.dur * speed_boost, 1)

        # Calculate current EU/t spend
        x = recipe.eut * eu_discount
        y = min(int(available_eut / x), max_parallels)
        total_eut = x * y

        # Debug info
        self.parent_context.log('Base GT++ OC stats:')
        self.parent_context.log(
            f'{available_eut=} {max_parallels=} {new_recipe_time=} {total_eut=} {y=}')

        # Attempt to GT OC the entire parallel set until no energy is left
        while total_eut < available_eut:
            oc_eut = total_eut * 4
            oc_dur = new_recipe_time / 2
            if oc_eut <= available_eut:
                if oc_dur < 1:
                    break
                self.parent_context.log('OC to')
                self.parent_context.log(f'{oc_eut=} {oc_dur=}')
                total_eut = oc_eut
                new_recipe_time = oc_dur
            else:
                break

        recipe.eut = total_eut
        recipe.dur = new_recipe_time
        recipe.I *= y
        recipe.O *= y

        return recipe

    def modify_gtplusplus_custom(self, recipe, max_parallels, speed_per_tier=1):
        available_eut = self.voltage_cutoffs[self.voltages.index(recipe.user_voltage)]

        x = recipe.eut
        y = min(int(available_eut / x), max_parallels)
        total_eut = x * y
        new_recipe_time = round(recipe.dur * (speed_per_tier) **
                                (self.voltages.index(recipe.user_voltage) + 1), 2)

        self.parent_context.log('Base GT++ OC stats:')
        self.parent_context.log(
            f'{available_eut=} {max_parallels=} {new_recipe_time=} {total_eut=} {y=}')

        while total_eut < available_eut:
            oc_eut = total_eut * 4
            oc_dur = new_recipe_time / 2
            if oc_eut <= available_eut:
                if oc_dur < 20:
                    break
                self.parent_context.log('OC to')
                self.parent_context.log(f'{oc_eut=} {oc_dur=}')
                total_eut = oc_eut
                new_recipe_time = oc_dur
            else:
                break

        recipe.eut = total_eut
        recipe.dur = new_recipe_time
        recipe.I *= y
        recipe.O *= y

        return recipe

    def modify_chemplant(self, recipe):
        require(
            recipe,
            [
                ['coils', str, 'calculating recipe duration (eg "nichrome").'],
                ['pipe_casings', str, 'calculating throughput multiplier (eg "steel").']
            ]
        )
        # assert 'solid_casings' in dir(recipe), 'Chem plant requires "solid_casings" argument (eg "vigorous laurenium")'

        chem_plant_pipe_casings = self.overclock_data['pipe_casings']
        if recipe.pipe_casings not in chem_plant_pipe_casings:
            raise RuntimeError(
                f'Expected chem pipe casings in {list(chem_plant_pipe_casings)}\ngot "{recipe.pipe_casings}". (More are allowed, I just haven\'t added them yet.)')

        recipe.dur /= self.overclock_data['coil_data'][recipe.coils]['multiplier']
        throughput_multiplier = chem_plant_pipe_casings[recipe.pipe_casings]
        recipe.I *= throughput_multiplier
        recipe.O *= throughput_multiplier

        recipe = self.modify_standard(recipe)

        return recipe

    def modify_zhuhai(self, recipe):
        recipe = self.modify_standard(recipe)
        parallel_count = (self.voltages.index(recipe.user_voltage) + 2) * 2
        recipe.O *= parallel_count
        return recipe

    def modify_ebf(self, recipe):
        require(
            recipe,
            [
                ['coils', str, 'calculating heat and perfect OCs for recipes (eg "nichrome").'],
                ['heat', int, 'calculating perfect OCs and heat requirement (eg "4300").'],
            ]
        )
        base_voltage = bisect_right(self.voltage_cutoffs, recipe.eut)
        user_voltage = self.voltages.index(recipe.user_voltage)
        oc_count = user_voltage - base_voltage

        actual_heat = self.overclock_data['coil_data'][recipe.coils]['heat'] + \
            100 * min(0, user_voltage - 2)
        excess_heat = actual_heat - recipe.heat
        eut_discount = 0.95 ** (excess_heat // 900)
        perfect_ocs = (excess_heat // 1800)

        recipe.eut = recipe.eut * 4**oc_count * eut_discount
        recipe.dur = recipe.dur / 2**oc_count / 2**max(min(perfect_ocs, oc_count), 0)

        return recipe

    def modify_pyrolyse(self, recipe):
        require(
            recipe,
            [
                ['coils', str, 'calculating recipe time (eg "nichrome").']
            ]
        )
        oc_count = self.calculate_standard_oc(recipe)
        recipe.eut = recipe.eut * 4**oc_count
        recipe.dur = recipe.dur / 2**oc_count / \
            self.overclock_data['coil_data'][recipe.coils]['multiplier']

        return recipe

    def modify_multismelter(self, recipe):
        require(
            recipe,
            [
                ['coils', str, 'calculating heat and perfect OCs for recipes (eg "nichrome").']
            ]
        )
        recipe.eut = 4
        recipe.dur = 500
        recipe = self.modify_standard(recipe)
        coil_list = list(self.overclock_data['coil_data'].keys())
        batch_size = 8 * 2**max(4, coil_list.index(recipe.coils))
        recipe.I *= batch_size
        recipe.O *= batch_size
        return recipe

    def modify_tgs(self, recipe):
        require(
            recipe,
            [
                ['saw_type', str, 'calculating throughput of TGS (eg "saw", "buzzsaw").']
            ]
        )
        saw_multipliers = {
            'saw': 1,
            'buzzsaw': 2,
            'chainsaw': 4,
        }
        assert recipe.saw_type in saw_multipliers, f'"saw_type" must be in {saw_multipliers}'

        oc_idx = self.voltages.index(recipe.user_voltage)
        t_tier = oc_idx + 1
        tgs_base_output = (2 * (t_tier**2) - (2 * t_tier) + 5) * 5
        tgs_wood_out = tgs_base_output * saw_multipliers[recipe.saw_type]

        assert len(
            recipe.O) <= 1, 'Automatic TGS overclocking only supported for single output - ask dev to support saplings'

        # Mutate final recipe
        if len(recipe.O) == 0:
            recipe.O = IngredientCollection(Ingredient('wood', tgs_wood_out))
        else:
            recipe.O = IngredientCollection(Ingredient(recipe.O._ings[0].name, tgs_wood_out))
        recipe.eut = self.voltage_cutoffs[oc_idx] - 1
        # print(oc_idx)
        recipe.dur = max(100 / (2**(oc_idx)), 1)

        return recipe

    def modify_utupu(self, recipe):
        require(
            recipe,
            [
                ['coils', str, 'calculating heat and perfect OCs for recipes (eg "nichrome").'],
                ['heat', int, 'calculating heat and perfect OCs for recipes (eg "4300").'],
            ]
        )

        # First do parallel step of GTpp
        if recipe.machine not in self.overclock_data['gtpp_stats']:
            raise RuntimeError(
                'Missing OC data for GT++ multi - add to gtnhClasses/overclocks.py:gtpp_stats')

        # Get per-machine boosts
        speed_boost, eut_discount, parallels_per_tier = self.overclock_data['gtpp_stats'][recipe.machine]
        speed_boost = 1 / (speed_boost + 1)

        # Calculate base parallel count and clip time to 1 tick
        available_eut = self.voltage_cutoffs[self.voltages.index(recipe.user_voltage)]
        max_parallels = (self.voltages.index(recipe.user_voltage) + 1) * parallels_per_tier
        new_recipe_time = max(recipe.dur * speed_boost, 1)

        # Calculate current EU/t spend
        x = recipe.eut * eut_discount
        y = min(int(available_eut / x), max_parallels)
        total_eut = x * y

        # Debug info
        self.parent_context.log('Base GT++ OC stats:')
        self.parent_context.log(
            f'{available_eut=} {max_parallels=} {new_recipe_time=} {total_eut=} {y=}')

        # Now do GT EBF OC
        base_voltage = bisect_right(self.voltage_cutoffs, total_eut)
        user_voltage = self.voltages.index(recipe.user_voltage)
        oc_count = user_voltage - base_voltage

        # + 100 * min(0, user_voltage - 1) # I assume there's no bonus heat on UT
        actual_heat = self.overclock_data['coil_data'][recipe.coils]['heat']
        excess_heat = actual_heat - recipe.heat
        eut_discount = 0.95 ** (excess_heat // 900)
        perfect_ocs = (excess_heat // 1800)

        recipe.eut = total_eut * 4**oc_count * eut_discount
        recipe.dur = new_recipe_time / 2**oc_count / 2**max(min(perfect_ocs, oc_count), 0)
        recipe.I *= y
        recipe.O *= y

        return recipe

    def modify_fusion(self, recipe):
        # Ignore "tier" and just use "mk" argument for OCs
        # start is also in "mk" notation
        require(
            recipe,
            [
                ['mk', int,
                    'overclocking fusion. mk = actual mark run at, start = base mk. (eg mk=3, start=2)'],
                ['start', int,
                    'overclocking fusion. mk = actual mark run at, start = base mk. (eg mk=3, start=2)'],
            ]
        )

        mk_oc = recipe.mk - recipe.start

        bonus = 1
        if recipe.mk == 4 and mk_oc > 0:
            bonus = 2
        recipe.eut = recipe.eut * (2**mk_oc * bonus)
        recipe.dur = recipe.dur / (2**mk_oc * bonus)
        recipe.user_voltage = self.voltages[bisect_right(self.voltage_cutoffs, recipe.eut)]
        recipe.machine = f'MK{recipe.mk} {recipe.machine}'
        return recipe

    def modify_turbine(self, recipe, fuel_type):
        require(
            recipe,
            [
                ['material', str, 'calculating power output (eg "infinity").'],
                ['size', str, 'calculating power output (eg "large").'],
            ]
        )

        fuel = recipe.I._ings[0].name
        material = recipe.material.lower()
        size = recipe.size.lower()

        turbine_data = self.parent_context.data['turbine_data']
        assert fuel in turbine_data['fuels'][fuel_type], f'Unsupported fuel "{fuel}"'
        assert material in turbine_data['materials'], f'Unsupported material "{material}"'
        assert size in turbine_data['rotor_size'], f'Unsupported size "{size}"'

        material_data = turbine_data['materials'][material]

        # TODO: For now, assume optimal eut/flow as calculated on spreadsheet
        if getattr(recipe, 'flow', None) is None:
            # Calculate optimal gas flow for turbine (in EU/t)
            optimal_eut = (
                material_data['mining speed']
                * turbine_data['rotor_size'][size]['multiplier']
                * 50
            )
            efficiency = (
                (material_data['tier'] * 10)
                + 100
                + turbine_data['rotor_size'][size]['efficiency']
            )

            burn_value = turbine_data['fuels'][fuel_type][fuel]
            optimalflow_l_per_t = math.floor(optimal_eut / burn_value)
            output_eut = math.floor(optimalflow_l_per_t * burn_value * efficiency / 100)
        else:
            raise NotImplementedError('Specifying "flow" feature not implemented yet')

        # print(f'{optimal_eut=}')
        # print(f'{optimal_flow_L_t=}')
        # print(f'{efficiency=}')
        # print(f'{output_eut=}')

        additional = []
        if fuel_type == 'steam_fuels':
            additional.append(Ingredient('(recycle) distilled water', optimalflow_l_per_t // 160))

        recipe.eut = 0
        recipe.dur = 1
        recipe.I._ings[0].quant = optimalflow_l_per_t
        recipe.O = IngredientCollection(*[
            Ingredient('EU', output_eut),
            *additional
        ])
        recipe.efficiency = f'{efficiency}%'

        return recipe

    def modify_xl_turbine(self, recipe, fuel_type):
        recipe = self.modify_turbine(recipe, fuel_type)
        recipe.I *= 16
        recipe.O *= 16

        return recipe

    def calculate_standard_oc(self, recipe):
        base_voltage = bisect_right(self.voltage_cutoffs, recipe.eut)
        user_voltage = self.voltages.index(recipe.user_voltage)
        oc_count = user_voltage - base_voltage
        if oc_count < 0:
            raise RuntimeError(
                f'Recipe has negative overclock! Min voltage is {base_voltage}, given OC voltage is {user_voltage}.\n{recipe}')
        return oc_count

    def modify_standard(self, recipe):
        oc_count = self.calculate_standard_oc(recipe)
        recipe.eut = recipe.eut * 4**oc_count
        recipe.dur = recipe.dur / 2**oc_count
        return recipe

    def modify_perfect(self, recipe):
        oc_count = self.calculate_standard_oc(recipe)
        recipe.eut = recipe.eut * 4**oc_count
        recipe.dur = recipe.dur / 4**oc_count
        return recipe

    def overclock_recipe(self, recipe, ignore_underclock=False):
        # Modifies recipe according to overclocks
        # By the time that the recipe arrives here, it should have a "user_voltage" argument which indicates
        # what the user is actually providing.
        self.ignore_underclock = ignore_underclock

        machine_overrides = {
            # GT multis
            'pyrolyse oven': self.modify_pyrolyse,
            'large chemical reactor': self.modify_perfect,
            'electric blast furnace': self.modify_ebf,
            'multi smelter': self.modify_multismelter,
            'circuit assembly line': self.modify_perfect,
            'fusion reactor': self.modify_fusion,

            'large gas turbine': lambda recipe: self.modify_turbine(recipe, 'gas_fuels'),
            'XL Turbo Gas Turbine': lambda recipe: self.modify_xl_turbine(recipe, 'gas_fuels'),

            'large steam turbine': lambda recipe: self.modify_turbine(recipe, 'steam_fuels'),
            'XL Turbo Steam Turbine': lambda recipe: self.modify_xl_turbine(recipe, 'steam_fuels'),

            # Basic GT++ multis
            'industrial centrifuge': self.modify_gtplusplus,
            'industrial material press': self.modify_gtplusplus,
            'industrial electrolyzer': self.modify_gtplusplus,
            'maceration stack': self.modify_gtplusplus,
            'wire factory': self.modify_gtplusplus,
            'industrial mixing machine': self.modify_gtplusplus,
            'industrial sifter': self.modify_gtplusplus,
            'large thermal refinery': self.modify_gtplusplus,
            'industrial wash plant': self.modify_gtplusplus,
            'industrial extrusion machine': self.modify_gtplusplus,
            'large processing factory': self.modify_gtplusplus,
            'industrial arc furnace': self.modify_gtplusplus,
            'large scale auto-assembler': self.modify_gtplusplus,
            'cutting factory controller': self.modify_gtplusplus,
            'boldarnator': self.modify_gtplusplus,
            'dangote - distillery': self.modify_gtplusplus,
            'thermic heating device': self.modify_gtplusplus,

            # Special GT++ multis
            'industrial coke oven': lambda recipe: self.modify_gtplusplus_custom(recipe, 24, speed_per_tier=0.96),
            'dangote - distillation tower': lambda recipe: self.modify_gtplusplus_custom(recipe, 12),
            'dangote': lambda recipe: self.modify_gtplusplus_custom(recipe, 12),
            'chemical plant': self.modify_chemplant,
            'zhuhai': self.modify_zhuhai,
            'tree growth simulator': self.modify_tgs,
            'industrial dehydrator': self.modify_utupu,
            'flotation cell regulator': self.modify_perfect,
            'isamill grinding machine': self.modify_perfect,
        }

        if getattr(recipe, 'do_not_overclock', False):
            return recipe

        if recipe.machine in machine_overrides:
            return machine_overrides[recipe.machine](recipe)
        else:
            return self.modify_standard(recipe)
