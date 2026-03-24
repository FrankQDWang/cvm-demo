import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet],
  templateUrl: './app.html',
  styleUrl: './app.css'
})
export class App {
  readonly title = '候选寻访工作台';
  readonly subtitle = '围绕岗位说明生成筛选建议、浏览候选人、查看简历要点并导出名单。';
}
