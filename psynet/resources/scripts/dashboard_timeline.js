$(document).ready(function() {
  $.each(timeline_modules["modules"], function() {
    $('.chart').append('<div class="progress ' + this['id'] + '" data-module-id="' + this['id'] + '" data-html="true">' + '<div class="progress-bar ' + this['id'] + '" aria-valuenow="60" aria-valuemin="0" aria-valuemax="100" style="width: 0%;"><span class="show ' + this['id'] + '">' + this['id'] + '</span></div></div>');
  });

  $('.progress').tooltip();

  $('.progress').click(function(data) {
    updateDetails($(this).data('module-id'))
  });

  var module_ids = timeline_modules["modules"].map(module_data => module_data['id'])
  get_data = {}
  get_data['module_ids'] = module_ids

  setInterval(function() {
    $.get('/module/progress_info', get_data)
      .done(function(data) {

        $.each(module_ids, function(index, module_id) {
          let has_target = data[module_id]['target_num_participants'] ? true : false
          let progress_percentage = Number((data[module_id]['progress'] * 100).toFixed(1))
          let text = module_id + ': ' + data[module_id]['started_num_participants'] + '/' + data[module_id]['finished_num_participants'] + (has_target ? '/' + data[module_id]['target_num_participants'] : '') + ' (started/finished' + (has_target ? '/target) ' + progress_percentage + '%' : ')')
          $('.show.' + module_id).text(text)
          if (data[module_id]['finished_num_participants'] > 0) {
            $('.progress-bar.' + module_id).css('width', progress_percentage + '%')
          }
        });
      });
  }, 2000);

  $('.progress').mouseenter(function(data) {
    updateTooltip($(this).data('module-id'))
  });
});

function updateDetails(module_id) {
  $("#element-details").load('/module/' + module_id)
}

function updateTooltip(module_id) {
  $.get('/module/' + module_id + '/tooltip', function(data) {
    $('.progress.' + module_id).tooltip('dispose').tooltip({title: data}).tooltip('show')
  });
}
