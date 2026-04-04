import unreal
from LevelUtilities import level_utils
from typing import List

import importlib
importlib.reload(level_utils)

editor_subsystem = unreal.UnrealEditorSubsystem()
editor_filter_lib = unreal.EditorFilterLibrary()
level_sequence_lib = unreal.LevelSequenceEditorBlueprintLibrary()
sequencer_tool = unreal.SequencerTools()
editor_level_lib = unreal.EditorLevelLibrary()
editor_actor_util = unreal.EditorActorSubsystem()
sys_lib = unreal.SystemLibrary()




def is_same_binding(binding_id_a, binding_id_b):
    guid_a_str = binding_id_a.get_editor_property("Guid").to_string()
    guid_b_str = binding_id_b.get_editor_property("Guid").to_string()
    return guid_a_str == guid_b_str


def get_binding_by_display_name(name, level_sequence):
    all_bindings = level_sequence.get_bindings()
    for binding in all_bindings:
        if binding.get_display_name() == name:
            return binding
    return None


def get_binding_by_binding_id(id: unreal.MovieSceneObjectBindingID, level_sequence):
    all_bindings = level_sequence.get_bindings()
    for binding in all_bindings:
        if is_same_binding(id, binding.get_binding_id()):
            return binding
    return None


def print_binding_info(binding_object: unreal.SequencerBindingProxy, level_sequence):
    display_name = binding_object.get_display_name()
    name = binding_object.get_name()
    tracks = binding_object.get_tracks()
    track_log_str = ""
    for track in tracks:
        track_name = track.get_display_name()
        section_log_str = ""
        sections = track.get_sections()
        for section in sections:
            print(section)
            section_log_str = "{}\n\t\tSection: {}".format(section_log_str, section.get_name())
            if isinstance(section, unreal.MovieScene3DAttachSection):
                info = get_attach_section_log_info(section, level_sequence)
                section_log_str = "{}\n{}".format(section_log_str, info)
        track_log_str = "{}\t-Track: {}\n{}\n".format(track_log_str, track_name, section_log_str)
    final_log = """
------Log Binding------
  Name: {}
  Display Name: {}
  Tracks: 
  {}
    """.format(name, display_name, track_log_str)
    print(final_log)
    

def get_binding_source_object(binding_object: unreal.SequencerBindingProxy, 
                              level_sequencer: unreal.MovieSceneSequence, 
                              master_sequencer: unreal.MovieSceneSequence = None):
    origin_objects = level_sequencer.locate_bound_objects(binding_object, None)
    if len(origin_objects) <= 0 and master_sequencer is not None:
        sub_sections = get_subsequence_sections(master_sequencer)
        target_section = None
        current_section = None
        for sub_section in sub_sections:
            if sub_section.get_sequence() == level_sequencer:
                target_section = sub_section
            if sub_section.get_sequence() == level_sequence_lib.get_focused_level_sequence():
                current_section = sub_section
        
        if target_section:
            level_sequence_lib.focus_level_sequence(target_section)
            level_sequence_lib.refresh_current_level_sequence()
            
        origin_objects = level_sequence_lib.get_bound_objects(binding_object.get_binding_id())
        
        if target_section and current_section:
            level_sequence_lib.focus_level_sequence(current_section)
            level_sequence_lib.refresh_current_level_sequence()
    
    if len(origin_objects) > 0:
        return origin_objects[0]
    return None


def print_binding_info_simple(binding_object: unreal.SequencerBindingProxy, level_sequencer):
    display_name = binding_object.get_display_name()
    name = binding_object.get_name()
    binding_guid = binding_object.get_binding_id().get_editor_property("Guid").to_string()
    origin_class = binding_object.get_possessed_object_class()
    origin_object = get_binding_source_object(binding_object, level_sequencer)
    # if origin_object is not None:
    #     actor_class = sys_lib.get_class_display_name(origin_object.static_class())
    #     if actor_class == "Actor":
    #         get_all_attachable_sockets_in_actor(origin_object)
            
    final_log = """
------Log Binding------
  Name: {}
  Display Name: {}
  Binding Guid: {}
  Class: {}
  Origin Object: {}
    """.format(name, display_name, binding_guid, origin_class, origin_object)
    print(final_log)
    

def get_attach_section_log_info(section: unreal.MovieScene3DAttachSection, level_sequence):
    name = section.get_name()
    binding_id = section.get_constraint_binding_id()
    binding = get_binding_by_binding_id(binding_id, level_sequence)
    binding_name = binding_id
    if binding is not None:
        binding_name = binding.get_display_name()
    component_name = section.attach_component_name
    socket_name = section.attach_socket_name
    log_str = """
            binding id: {}
            attach component: {}
            attach socket: {}
        """.format(name, 
                   binding_name, 
                   component_name, 
                   socket_name)
    return log_str


def attach_binding_to(binding: unreal.SequencerBindingProxy, 
                      target_to_attach: unreal.SequencerBindingProxy, 
                      attach_component, 
                      attach_socket, 
                      start_frame, end_frame,
                      level_sequencer: unreal.MovieSceneSequence):
    exist_tracks = binding.find_tracks_by_type(unreal.MovieScene3DAttachTrack)
    for exist_track in exist_tracks:
        binding.remove_track(exist_track)
    
    exist_track = binding.add_track(unreal.MovieScene3DAttachTrack)
    attach_section = exist_track.add_section()
    
    # attach_binding_id = get_current_opened_sequence().make_binding_id(target_to_attach, unreal.MovieSceneObjectBindingSpace.ROOT)
    
    attach_binding_id = unreal.MovieSceneSequenceExtensions.get_portable_binding_id(get_current_opened_sequence(), level_sequencer, target_to_attach)
    
    attach_section.set_constraint_binding_id(attach_binding_id)
    attach_section.attach_component_name = attach_component
    attach_section.attach_socket_name = attach_socket
    attach_section.set_start_frame(start_frame)
    attach_section.set_end_frame(end_frame)
    attach_section.attachment_location_rule = unreal.AttachmentRule.KEEP_RELATIVE
    attach_section.attachment_rotation_rule = unreal.AttachmentRule.KEEP_RELATIVE
    attach_section.detachment_location_rule = unreal.DetachmentRule.KEEP_RELATIVE
    attach_section.detachment_rotation_rule = unreal.DetachmentRule.KEEP_RELATIVE
    print("Attaching {} to {}.{}.{} at range[{}-{}]".format(
        binding.get_display_name(),
        target_to_attach.get_display_name(),
        attach_component,
        attach_socket,
        start_frame, end_frame
    ))

    # transform_track = binding.add_track(unreal.MovieScene3DTransformTrack)
    # transform_section = transform_track.add_section()
    # transform_section.set_start_frame(start_frame)
    # transform_section.set_end_frame(end_frame)


def get_attached_binding(binding: unreal.SequencerBindingProxy, level_sequence):
    exist_tracks = binding.find_tracks_by_type(unreal.MovieScene3DAttachTrack)
    for exist_track in exist_tracks:
        for section in exist_track.get_sections():
            attach_binding_id = section.get_constraint_binding_id()
            
            all_level_sequence = get_subsequences(level_sequence)
            all_level_sequence.append(level_sequence)
            
            for sub_level_sequence in all_level_sequence:
                attach_binding = get_binding_by_binding_id(attach_binding_id, sub_level_sequence)
                if attach_binding is not None:
                    return [attach_binding, section.attach_component_name, section.attach_socket_name, section.get_start_frame(), section.get_end_frame()]
    return None


def get_subsequences(main_sequence):
    subsequences = []
    for track in main_sequence.get_master_tracks():
        if track.get_class().get_name() == "MovieSceneSubTrack":
            for section in track.get_sections():
                subsequences.append(section.get_sequence())
    return subsequences


def get_subsequence_sections(main_sequence) -> List[unreal.MovieSceneSubSection]:
    subsequences = []
    for track in main_sequence.get_master_tracks():
        if track.get_class().get_name() == "MovieSceneSubTrack":
            for section in track.get_sections():
                subsequences.append(section)
    return subsequences


def get_all_attachable_sockets_in_actor(actor: unreal.Actor):
    if not isinstance(actor, unreal.Actor):
        return {}
    root_component = actor.root_component
    attachable_components = {}

    if root_component is not None:
        children_components = root_component.get_children_components(True)
        for children_component in children_components:
            if isinstance(children_component, unreal.SceneComponent):
                attachable_components[children_component.get_name()] = children_component.get_all_socket_names()
                
    return attachable_components


def get_current_opened_sequence():
    current_level_sequence = level_sequence_lib.get_current_level_sequence()
    return current_level_sequence


def get_current_focused_sequence():
    current_focused_sequence = level_sequence_lib.get_focused_level_sequence()
    return current_focused_sequence


def add_actor_to_sequence(actor, level_sequence):
    new_binding = level_sequence.add_possessable(actor)
    return new_binding


if __name__ == "__main__":
    # all_actors = editor_level_lib.get_all_level_actors()
    # level_sequence_actor = editor_filter_lib.by_class(all_actors, unreal.LevelSequenceActor)[0]
    # level_sequence = level_sequence_actor.level_sequence_asset
    # light_test = editor_filter_lib.by_class(all_actors, unreal.SpotLight)[0]
    # light_binding = level_sequence.add_possessable(light_test)
    # track = light_binding.add_track(unreal.MovieScene3DAttachTrack)
    # 
    # target_character_binding = get_binding_by_display_name(BP_NAME, level_sequence)
    # attach_binding_to(track, target_character_binding, "LightAttachment", "pelvis", 0, 1)
    # light_binding = get_binding_by_display_name("SpotLight", level_sequence)
    # print_binding_info(light_binding, level_sequence)
    
    current_level_sequence = level_sequence_lib.get_current_level_sequence()
    # print(current_level_sequence)
    # all_bindings = current_level_sequence.get_bindings()
    # for binding in all_bindings:
    #     print(binding.get_display_name())

    subsequences = get_subsequences(current_level_sequence)
    print(subsequences)
    subsequences.append(current_level_sequence)
    for subsequence in subsequences:
        all_bindings = subsequence.get_bindings()
        for binding in all_bindings:
            print_binding_info_simple(binding, subsequence)